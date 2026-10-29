from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# Photos moved in from another installation pass through this temporary folder only.
TRANSFER_FOLDER = "trasferimento/"

TransferPublicId = Annotated[
    str,
    StringConstraints(pattern=r"^trasferimento/[A-Za-z0-9_/-]{1,150}\.(jpg|jpeg|png|webp)$"),
]


class TransferSignatureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["upload", "destroy"]
    public_ids: list[TransferPublicId] = Field(min_length=1, max_length=1000)


class TransferSignature(BaseModel):
    # Cloudinary's id: the key without the image extension, as the browser must send it.
    public_id: str
    timestamp: str
    api_key: str
    signature: str
    url: str
    delivery_url: str


class TransferSignatures(BaseModel):
    items: list[TransferSignature]
