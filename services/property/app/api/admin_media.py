"""Admin panel: tools for moving listing photos in from another installation."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import get_media_transfer_service, require_staff
from app.schemas.media import TransferSignatureRequest, TransferSignatures
from app.services.media_transfer import MediaTransferService

router = APIRouter(prefix="/admin/media", tags=["admin"], dependencies=[Depends(require_staff)])


@router.post("/transfer-signatures", response_model=TransferSignatures)
async def transfer_signatures(
    request: TransferSignatureRequest,
    service: Annotated[MediaTransferService, Depends(get_media_transfer_service)],
) -> TransferSignatures:
    return service.signatures(request)
