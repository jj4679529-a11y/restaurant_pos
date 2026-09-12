from app.models.enums import UserRole
from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    # Legacy bootstrap admins may have been seeded while ADMIN_PASSWORD was
    # intentionally blank.  User creation and replacement forbid blanks, but
    # login must still be able to verify that existing Argon2 hash.
    password: str = Field(max_length=1024)


class AuthenticatedUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    username: str
    role: UserRole


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: AuthenticatedUserResponse
