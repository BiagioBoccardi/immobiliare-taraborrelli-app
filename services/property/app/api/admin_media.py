"""Admin panel: moving listing photos in from another installation."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import get_media_transfer_service, require_staff
from app.schemas.media import TransferCleanup, TransferSignature
from app.services.media_transfer import MediaTransferService

router = APIRouter(prefix="/admin/media", tags=["admin"], dependencies=[Depends(require_staff)])

Service = Annotated[MediaTransferService, Depends(get_media_transfer_service)]


@router.post("/transfer-signature", response_model=TransferSignature)
async def transfer_signature(service: Service) -> TransferSignature:
    return service.signature()


@router.post("/transfer-cleanup", response_model=TransferCleanup)
async def transfer_cleanup(service: Service) -> TransferCleanup:
    return await service.cleanup()
