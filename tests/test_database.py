from app.database.connection import check_postgres_connection


def test_postgres_connection() -> None:
    assert check_postgres_connection() is True
