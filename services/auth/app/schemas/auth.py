import uuid
from datetime import datetime
from typing import Annotated, Literal

from py_common.security import Role
from pydantic import BaseModel, ConfigDict, StringConstraints

from app.models.enums import ConsentPurpose, ConsentSource
from app.schemas.common import Email, Password, PersonName, PolicyVersion


class RegistrationConsent(BaseModel):
    privacy_accepted: Literal[True]
    privacy_policy_version: PolicyVersion
    marketing_accepted: bool = False


class RegisterIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: Email
    password: Password
    full_name: PersonName
    consent: RegistrationConsent
    source: Literal[ConsentSource.APP, ConsentSource.WEB] = ConsentSource.APP


class LoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: Email
    # No length rules here: they are checked at registration, login only compares.
    password: str


class ForgotPasswordIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: Email


class ResetPasswordIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: Email
    code: Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^\d{6}$")]
    new_password: Password


class RefreshIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105
    expires_in: int  # seconds until the access token expires


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: Role
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


class StaffCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: Email
    password: Password
    full_name: PersonName
    role: Literal[Role.STAFF, Role.ADMIN] = Role.STAFF


class UserUpdate(BaseModel):
    """Admin change to an account. Only the fields that are sent are changed."""

    model_config = ConfigDict(extra="forbid")

    role: Role | None = None
    is_active: bool | None = None
    full_name: PersonName | None = None


class ConsentChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: ConsentPurpose
    granted: bool
    policy_version: PolicyVersion
    source: Literal[ConsentSource.APP, ConsentSource.WEB] = ConsentSource.APP


class ConsentStatus(BaseModel):
    purpose: ConsentPurpose
    granted: bool
    policy_version: str
    recorded_at: datetime


class ConsentRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    purpose: ConsentPurpose
    granted: bool
    policy_version: str
    source: ConsentSource
    recorded_at: datetime


class UserExport(BaseModel):
    """GDPR export: everything the auth service stores about the user."""

    user: UserOut
    consents: list[ConsentRecordOut]
    exported_at: datetime
