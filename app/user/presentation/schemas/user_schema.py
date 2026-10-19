from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from user.domain.entities.user import User


class UserCreateSchema(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class UserLoginSchema(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    remember: bool = True


class UserResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, user: User) -> "UserResponseSchema":
        return cls(
            id=user.id,
            email=user.email,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )


class LoginResponseSchema(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponseSchema
