import re
from typing import Annotated

from pydantic import AfterValidator, StringConstraints

_PHONE_SEPARATORS = re.compile(r"[\s\-./()]")
_PHONE_PATTERN = re.compile(r"^\+?\d{6,15}$")


def _normalize_phone(value: str) -> str:
    compact = _PHONE_SEPARATORS.sub("", value)
    if compact.startswith("00"):
        compact = "+" + compact[2:]
    if not _PHONE_PATTERN.match(compact):
        raise ValueError("invalid phone number")
    return compact


Phone = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=25), AfterValidator(_normalize_phone)
]
PersonName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
Municipality = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]
EmailText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
]
PolicyVersion = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)
]
