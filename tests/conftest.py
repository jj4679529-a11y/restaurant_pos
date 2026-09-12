from collections.abc import Generator

import pytest
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.connection import engine


@pytest.fixture(autouse=True)
def jwt_test_settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "restaurant-pos-test-jwt-secret")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def db() -> Generator[Session, None, None]:
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()
