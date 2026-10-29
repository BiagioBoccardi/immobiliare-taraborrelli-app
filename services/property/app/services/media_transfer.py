"""Moving listing photos in from another installation, through a temporary folder.

The browser uploads each photo to `trasferimento/` with a signature that expires after an
hour, the admin panel adds it to its property through the normal photo upload (same type
and size checks), and the temporary folder is then emptied.
"""

from py_common.errors import ConflictError

from app.schemas.media import TRANSFER_FOLDER, TransferCleanup, TransferSignature
from app.storage.base import MediaStorage
from app.storage.cloudinary import CloudinaryMediaStorage


class MediaTransferService:
    def __init__(self, storage: MediaStorage) -> None:
        self._storage = storage

    def _cloudinary(self) -> CloudinaryMediaStorage:
        if not isinstance(self._storage, CloudinaryMediaStorage):
            raise ConflictError(
                "Photo transfer needs the Cloudinary storage", code="transfer_unavailable"
            )
        return self._storage

    def signature(self) -> TransferSignature:
        return TransferSignature.model_validate(
            self._cloudinary().folder_upload_signature(TRANSFER_FOLDER)
        )

    async def cleanup(self) -> TransferCleanup:
        deleted = await self._cloudinary().delete_folder(TRANSFER_FOLDER)
        return TransferCleanup(deleted=deleted)
