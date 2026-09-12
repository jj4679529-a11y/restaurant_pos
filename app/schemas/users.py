from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import UserRole


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=1024)
    role: UserRole

    @field_validator("name", "username")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value must not be blank")
        return value

    @field_validator("password")
    @classmethod
    def require_non_blank_password(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Password must not be blank")
        return value


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    username: str | None = Field(default=None, min_length=1, max_length=64)
    password: str | None = Field(default=None, min_length=1, max_length=1024)
    role: UserRole | None = None
    is_active: bool | None = None

    @field_validator("name", "username")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Value must not be blank")
        return value

    @field_validator("password")
    @classmethod
    def require_non_blank_replacement_password(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Password must not be blank")
        return value


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    username: str
    role: UserRole
    is_active: bool
