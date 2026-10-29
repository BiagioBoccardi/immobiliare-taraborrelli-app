"""Signed browser uploads to a temporary folder, to move photos from another installation.

The browser uploads each photo to `trasferimento/`, the admin panel then adds it to its
property through the normal photo upload, and finally deletes the temporary copy.
"""

from py_common.errors import ConflictError

from app.schemas.media import TransferSignatureRequest, TransferSignatures
from app.storage.base import MediaStorage
from app.storage.cloudinary import CloudinaryMediaStorage


class MediaTransferService:
    def __init__(self, storage: MediaStorage) -> None:
        self._storage = storage

    def signatures(self, request: TransferSignatureRequest) -> TransferSignatures:
        if not isinstance(self._storage, CloudinaryMediaStorage):
            raise ConflictError(
                "Photo transfer needs the Cloudinary storage", code="transfer_unavailable"
            )
        items = [
            self._storage.browser_signature(request.action, public_id)
            for public_id in request.public_ids
        ]
        return TransferSignatures.model_validate({"items": items})
