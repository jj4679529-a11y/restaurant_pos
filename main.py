from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.health import router as health_router
from app.api.router import api_router
from app.services.errors import ServiceError
from app.core.config import get_settings
from app.database.connection import check_postgres_connection
from app.database.connection import SessionLocal
from app.telegram.runtime import TelegramRuntime

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    check_postgres_connection()
    worker = TelegramRuntime(SessionLocal, get_settings())
    worker.start()
    try:
        yield
    finally:
        await asyncio.to_thread(worker.stop)


app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(api_router)


@app.exception_handler(ServiceError)
async def service_error_handler(_request: Request, exc: ServiceError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )
