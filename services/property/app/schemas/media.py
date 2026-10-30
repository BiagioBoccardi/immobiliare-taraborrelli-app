from pydantic import BaseModel

# Photos moved in from another installation pass through this temporary folder only.
TRANSFER_FOLDER = "trasferimento"


class TransferSignature(BaseModel):
    """Lets the browser upload into the transfer folder for an hour."""

    url: str
    api_key: str
    timestamp: str
    folder: str
    signature: str


class TransferCleanup(BaseModel):
    deleted: int
