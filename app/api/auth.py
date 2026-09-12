from fastapi import APIRouter, status

from app.api.deps import DbSession
from app.schemas.auth import LoginRequest, LoginResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
def login(data: LoginRequest, db: DbSession):
    result = auth_service.authenticate(db, data.username, data.password)
    return {
        "access_token": result.access_token,
        "token_type": "bearer",
        "user": result.user,
    }
