from typing import Annotated

from pydantic import AfterValidator, StringConstraints


def _lower(value: str) -> str:
    return value.lower()


Email = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
    AfterValidator(_lower),
]
Password = Annotated[str, StringConstraints(min_length=10, max_length=128)]
PersonName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
PolicyVersion = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)
]
