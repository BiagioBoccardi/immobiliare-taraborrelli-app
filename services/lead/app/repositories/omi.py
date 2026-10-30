from collections.abc import Sequence
from typing import Protocol

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.omi import OmiImport, OmiQuote, OmiZone


class OmiRepository(Protocol):
    async def replace_all(
        self, record: OmiImport, quotes: Sequence[OmiQuote], zones: Sequence[OmiZone]
    ) -> None: ...

    async def latest_import(self) -> OmiImport | None: ...

    async def zones_around(self, longitude: float, latitude: float) -> Sequence[OmiZone]: ...

    async def quotes_of_zone(
        self, municipality_code: str, zone_code: str
    ) -> Sequence[OmiQuote]: ...


class SqlOmiRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def replace_all(
        self, record: OmiImport, quotes: Sequence[OmiQuote], zones: Sequence[OmiZone]
    ) -> None:
        """Swaps the data in use in one transaction: estimates never see half an import."""
        await self._session.execute(delete(OmiQuote))
        await self._session.execute(delete(OmiZone))
        self._session.add(record)
        self._session.add_all([*quotes, *zones])
        await self._session.commit()

    async def latest_import(self) -> OmiImport | None:
        return await self._session.scalar(
            select(OmiImport).order_by(OmiImport.imported_at.desc(), OmiImport.id.desc()).limit(1)
        )

    async def zones_around(self, longitude: float, latitude: float) -> Sequence[OmiZone]:
        """Zones whose bounding box contains the point: the exact test is done in Python."""
        rows = await self._session.scalars(
            select(OmiZone).where(
                OmiZone.min_lon <= longitude,
                OmiZone.max_lon >= longitude,
                OmiZone.min_lat <= latitude,
                OmiZone.max_lat >= latitude,
            )
        )
        return rows.all()

    async def quotes_of_zone(self, municipality_code: str, zone_code: str) -> Sequence[OmiQuote]:
        rows = await self._session.scalars(
            select(OmiQuote).where(
                OmiQuote.municipality_code == municipality_code, OmiQuote.zone_code == zone_code
            )
        )
        return rows.all()
