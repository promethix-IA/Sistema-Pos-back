from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from shared.subscription import plan_label, subscription_state
from user.domain.entities.user import User


class UserCreateSchema(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: str | None = None
    plan: str | None = None


class UserRolePatch(BaseModel):
    role: str = Field(min_length=3, max_length=40)


class UserSubscriptionPatch(BaseModel):
    action: str = Field(min_length=3, max_length=40)


class UserDesktopPatch(BaseModel):
    enabled: bool | None = None
    channel: str | None = None
    updates_until: str | None = None


class UserLoginSchema(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    remember: bool = True


class PasswordEmailSchema(BaseModel):
    email: EmailStr


class PasswordCodeSchema(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=12)


class PasswordResetSchema(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=12)
    password: str = Field(min_length=8, max_length=128)


class UserResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    is_active: bool
    role: str
    owner_id: int | None = None
    plan: str = ""
    plan_label: str = "Libre"
    plan_expires_at: datetime | None = None
    subscription_status: str = "activo"
    desktop_download: bool = False
    desktop_channel: str = "windows10-11"
    desktop_updates_until: str = ""
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, user: User) -> "UserResponseSchema":
        return cls(
            id=user.id,
            email=user.email,
            is_active=user.is_active,
            role=user.role,
            owner_id=user.owner_id,
            plan=user.plan or "",
            plan_label=plan_label(user.plan),
            plan_expires_at=user.plan_expires_at,
            subscription_status=subscription_state(user),
            desktop_download=bool(user.desktop_download),
            desktop_channel=user.desktop_channel or "windows10-11",
            desktop_updates_until=user.desktop_updates_until or "",
            created_at=user.created_at,
            updated_at=user.updated_at,
        )


class LoginResponseSchema(BaseModel):
    access_token: str = ""
    token_type: str = "cookie"
    csrf_token: str = ""
    user: UserResponseSchema


class MeResponseSchema(UserResponseSchema):
    csrf_token: str = ""
