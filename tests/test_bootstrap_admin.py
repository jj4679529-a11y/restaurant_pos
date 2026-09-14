from unittest.mock import MagicMock

import pytest

import bootstrap_admin
from app.core.security import verify_password
from app.models import UserRole


@pytest.mark.parametrize("url", [None, "", "not-a-url", "sqlite:///restaurant_pos", "postgresql://localhost/other"])
def test_bootstrap_rejects_wrong_target(url):
    with pytest.raises(ValueError):
        bootstrap_admin.validate_database_url(url)


def test_bootstrap_accepts_postgresql_target():
    url = "postgresql+psycopg://postgres@localhost/restaurant_pos"
    assert bootstrap_admin.validate_database_url(url) == url


def factory_with_empty_users():
    factory = MagicMock()
    factory.return_value.__enter__.return_value.scalar.return_value = None
    session = factory.begin.return_value.__enter__.return_value
    session.scalar.return_value = None
    session.scalars.return_value.one_or_none.return_value = None
    return factory, session


def test_bootstrap_creates_admin_using_production_hash():
    factory, session = factory_with_empty_users()
    assert bootstrap_admin.bootstrap(factory, lambda _: "test-bootstrap-password")
    user = session.add.call_args.args[0]
    assert (user.username, user.name, user.role, user.is_active) == (
        "admin", "Administrator", UserRole.ADMIN, True,
    )
    assert user.password_hash.startswith("$argon2id$")
    assert verify_password("test-bootstrap-password", user.password_hash)
    assert "LOCK TABLE users" in str(session.execute.call_args.args[0])
    session.flush.assert_called_once()
    factory.begin.return_value.__exit__.assert_called_once_with(None, None, None)


def test_existing_admin_skips_password_prompt_and_writes():
    factory, session = factory_with_empty_users()
    factory.return_value.__enter__.return_value.scalar.return_value = 1
    prompt = MagicMock()
    assert bootstrap_admin.bootstrap(factory, prompt) is False
    prompt.assert_not_called()
    factory.begin.assert_not_called()
    session.add.assert_not_called()


def test_admin_created_during_prompt_is_not_duplicated():
    factory, session = factory_with_empty_users()
    session.scalar.return_value = 1
    assert bootstrap_admin.bootstrap(factory, lambda _: "test-password") is False
    session.add.assert_not_called()


@pytest.mark.parametrize("answers", [("", ""), ("   ", "   "), ("one", "two")])
def test_invalid_password_does_not_write(answers):
    factory, session = factory_with_empty_users()
    values = iter(answers)
    with pytest.raises(ValueError):
        bootstrap_admin.bootstrap(factory, lambda _: next(values))
    factory.begin.assert_not_called()
    session.add.assert_not_called()


def test_occupied_username_is_not_modified():
    factory, session = factory_with_empty_users()
    session.scalar.side_effect = [None, 7]
    with pytest.raises(ValueError, match="already occupied"):
        bootstrap_admin.bootstrap(factory, lambda _: "test-password")
    session.add.assert_not_called()


def test_cli_requires_environment_even_if_dotenv_exists(monkeypatch, capsys):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert bootstrap_admin.main() == 1
    assert "environment variable is required" in capsys.readouterr().err


def test_cli_does_not_print_database_exception(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/restaurant_pos")
    monkeypatch.setattr("sys.argv", ["bootstrap_admin.py"])
    monkeypatch.setattr(bootstrap_admin, "bootstrap", MagicMock(side_effect=RuntimeError("secret-value")))
    assert bootstrap_admin.main() == 1
    output = capsys.readouterr()
    assert "secret-value" not in output.out + output.err


def test_cli_success_message(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/restaurant_pos")
    monkeypatch.setattr("sys.argv", ["bootstrap_admin.py"])
    monkeypatch.setattr(bootstrap_admin, "bootstrap", MagicMock(return_value=True))
    assert bootstrap_admin.main() == 0
    assert capsys.readouterr().out == "Admin created successfully. Username: admin\n"
