"""OMI quotations in use for the automatic estimate: import from the admin panel and lookup."""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from py_common.errors import AppError, NotFoundError

from app.models.omi import OmiImport, OmiQuote, OmiZone
from app.repositories.omi import OmiRepository
from app.schemas.omi import OmiImportOut, OmiImportResult, OmiWarning
from app.services.omi_files import (
    OmiFileError,
    ParsedZone,
    bounding_box,
    contains,
    parse_perimeters,
    parse_quotes,
    parse_zone_descriptions,
)

logger = logging.getLogger(__name__)

MAX_EXAMPLES = 10


def utcnow() -> datetime:
    return datetime.now(UTC)


class OmiImportError(AppError):
    status_code = 422


@dataclass(frozen=True)
class UploadedFile:
    name: str
    data: bytes


@dataclass(frozen=True)
class ZoneMatch:
    """The OMI zone of a point, with its residential quotations."""

    municipality: str
    zone_code: str
    zone_description: str | None
    semester: str
    quotes: Sequence[OmiQuote]


def _warning(code: str, items: Sequence[str]) -> OmiWarning | None:
    if not items:
        return None
    return OmiWarning.model_validate(
        {"code": code, "count": len(items), "examples": list(items[:MAX_EXAMPLES])}
    )


class OmiService:
    def __init__(self, repository: OmiRepository, clock: Callable[[], datetime] = utcnow) -> None:
        self._repo = repository
        self._clock = clock

    async def import_files(
        self,
        quotes_file: UploadedFile,
        zones_file: UploadedFile | None,
        perimeter_files: Sequence[UploadedFile],
    ) -> OmiImportResult:
        """Replaces the OMI data in use with the files downloaded from the Agenzia delle Entrate."""
        try:
            parsed = parse_quotes(quotes_file.data, quotes_file.name)
            descriptions = (
                parse_zone_descriptions(zones_file.data, zones_file.name) if zones_file else {}
            )
            perimeters: list[ParsedZone] = []
            semesters = {parsed.semester}
            for file in perimeter_files:
                semester, found = parse_perimeters(file.data, file.name)
                perimeters.extend(found)
                semesters.add(semester)
        except OmiFileError as exc:
            raise OmiImportError(
                "The file is not an OMI file or cannot be read",
                code=exc.code,
                details={"file": exc.file_name},
            ) from exc
        if not parsed.quotes:
            raise OmiImportError(
                "No residential quotation found", code="omi_no_quotes",
                details={"file": quotes_file.name},
            )  # fmt: skip
        if not perimeters:
            raise OmiImportError("No zone perimeter found", code="omi_no_perimeters")

        # The perimeters use the administrative cadastral code; split municipalities may use
        # the cadastral one in some files: both lead to the same quotations.
        codes = {q.municipality_code for q in parsed.quotes}
        aliases = {q.alternative_code: q.municipality_code for q in parsed.quotes}
        names = {q.municipality_code: q.municipality for q in parsed.quotes}
        quoted_zones = {(q.municipality_code, q.zone_code) for q in parsed.quotes}

        zones: list[OmiZone] = []
        mapped: set[tuple[str, str]] = set()
        orphan_perimeters: list[str] = []
        for perimeter in perimeters:
            code = perimeter.municipality_code
            code = code if code in codes else aliases.get(code, code)
            if (code, perimeter.zone_code) not in quoted_zones:
                orphan_perimeters.append(f"{code} {perimeter.zone_code}")
                continue
            min_lon, min_lat, max_lon, max_lat = bounding_box(perimeter.polygons)
            mapped.add((code, perimeter.zone_code))
            zones.append(
                OmiZone(
                    municipality_code=code,
                    zone_code=perimeter.zone_code,
                    polygons=perimeter.polygons,
                    min_lon=min_lon,
                    min_lat=min_lat,
                    max_lon=max_lon,
                    max_lat=max_lat,
                )
            )

        quotes = [
            OmiQuote(
                municipality_code=q.municipality_code,
                municipality=q.municipality,
                zone_code=q.zone_code,
                zone_description=descriptions.get((q.municipality_code, q.zone_code)),
                omi_type=q.omi_type,
                state=q.state,
                prevalent=q.prevalent,
                sale_min=q.sale_min,
                sale_max=q.sale_max,
            )
            for q in parsed.quotes
        ]
        unmapped = sorted(f"{names[code]} {zone}" for code, zone in quoted_zones - mapped)
        known_semesters = sorted(s for s in semesters if s)
        semester = parsed.semester or (known_semesters[0] if known_semesters else "")
        record = OmiImport(
            semester=semester,
            quotes=len(quotes),
            zones=len(zones),
            municipalities=sorted({names[code] for code, _ in mapped}),
            imported_at=self._clock(),
        )
        await self._repo.replace_all(record, quotes, zones)
        logger.info(
            "omi data imported",
            extra={"semester": semester, "omi_quotes": len(quotes), "omi_zones": len(zones)},
        )
        warnings = [
            w
            for w in (
                _warning("zone_without_perimeter", unmapped),
                _warning("perimeter_without_quotes", sorted(set(orphan_perimeters))),
                _warning("semester_mismatch", known_semesters if len(known_semesters) > 1 else []),
            )
            if w is not None
        ]
        if parsed.skipped_rows:
            warnings.append(OmiWarning(code="rows_skipped", count=parsed.skipped_rows))
        return OmiImportResult(
            **OmiImportOut.model_validate(record).model_dump(), warnings=warnings
        )

    async def current(self) -> OmiImportOut:
        record = await self._repo.latest_import()
        if record is None:
            raise NotFoundError("OMI data not loaded yet", code="omi_not_loaded")
        return OmiImportOut.model_validate(record)

    async def find_zone(self, longitude: float, latitude: float) -> ZoneMatch | None:
        """The OMI zone containing the point, or None outside the loaded zones."""
        candidates = [
            zone
            for zone in await self._repo.zones_around(longitude, latitude)
            if contains(zone.polygons, longitude, latitude)
        ]
        if not candidates:
            return None
        # Rare overlaps at the borders: the smallest zone is the most specific one.
        zone = min(candidates, key=lambda z: (z.max_lon - z.min_lon) * (z.max_lat - z.min_lat))
        quotes = await self._repo.quotes_of_zone(zone.municipality_code, zone.zone_code)
        record = await self._repo.latest_import()
        if not quotes or record is None:
            return None
        return ZoneMatch(
            municipality=quotes[0].municipality,
            zone_code=zone.zone_code,
            zone_description=quotes[0].zone_description,
            semester=record.semester,
            quotes=quotes,
        )
