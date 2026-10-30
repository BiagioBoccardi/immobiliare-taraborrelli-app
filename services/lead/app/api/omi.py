"""OMI quotations for the automatic estimate, loaded from the admin panel (staff only)."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, status

from app.core.dependencies import get_omi_service, require_staff
from app.schemas.omi import OmiImportOut, OmiImportResult
from app.services.omi import OmiService, UploadedFile
from app.services.omi_files import MAX_FILE_BYTES

router = APIRouter(prefix="/omi", tags=["staff"], dependencies=[Depends(require_staff)])

Service = Annotated[OmiService, Depends(get_omi_service)]


async def _read(upload: UploadFile) -> UploadedFile:
    # One byte more than the limit is enough to recognize a file that is too large.
    return UploadedFile(name=upload.filename or "file", data=await upload.read(MAX_FILE_BYTES + 1))


@router.get("", response_model=OmiImportOut)
async def current_omi_data(service: Service) -> OmiImportOut:
    return await service.current()


@router.post("", status_code=status.HTTP_201_CREATED, response_model=OmiImportResult)
async def import_omi_data(
    service: Service,
    quotes: Annotated[UploadFile, File(description="Quotations file (..._VALORI.csv)")],
    perimeters: Annotated[
        list[UploadFile], File(description="Zone perimeters (.kmz or .kml), one or more")
    ],
    zones: Annotated[UploadFile | None, File(description="Zones file (..._ZONE.csv)")] = None,
) -> OmiImportResult:
    return await service.import_files(
        await _read(quotes),
        await _read(zones) if zones is not None else None,
        [await _read(file) for file in perimeters],
    )
