"""Console-only, admin-only bootstrap for an existing PostgreSQL database."""

import getpass
import os
import sys
import warnings


def validate_database_url(value: str | None) -> str:
    from sqlalchemy.engine import make_url

    if not value:
        raise ValueError("DATABASE_URL environment variable is required.")
    try:
        url = make_url(value)
    except Exception:
        raise ValueError("DATABASE_URL is invalid.") from None
    if url.get_backend_name() != "postgresql" or url.database != "restaurant_pos":
        raise ValueError("Expected PostgreSQL database restaurant_pos.")
    return value


def bootstrap(session_factory, prompt=getpass.getpass) -> bool:
    from sqlalchemy import select, text

    from app.models import User, UserRole
    from app.seed.config import SeedResult
    from app.seed.users import seed_admin

    with session_factory() as session:
        if session.scalar(select(User.id).where(User.role == UserRole.ADMIN).limit(1)):
            return False

    # Refuse environments where getpass would fall back to echoing the password.
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        password = prompt("New POS admin password: ")
        confirmation = prompt("Confirm POS admin password: ")
    if not password.strip():
        raise ValueError("Password must not be blank.")
    if password != confirmation:
        raise ValueError("Passwords do not match.")

    with session_factory.begin() as session:
        # Serialize competing bootstraps and users-table writes. Never hold the
        # lock while waiting for keyboard input.
        session.execute(text("LOCK TABLE users IN SHARE ROW EXCLUSIVE MODE"))
        if session.scalar(select(User.id).where(User.role == UserRole.ADMIN).limit(1)):
            return False
        if session.scalar(select(User.id).where(User.username == "admin")):
            raise ValueError("Username admin is already occupied. Nothing changed.")
        result = SeedResult(admin_created=False)
        seed_admin(session, "admin", password, "Administrator", result)
        session.flush()
    return True


def main() -> int:
    try:
        validate_database_url(os.environ.get("DATABASE_URL"))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    try:
        from app.database.connection import SessionLocal, engine

        if sys.argv[1:] == ["--self-test"]:
            from app.core.security import hash_password, verify_password
            from app.models import User, UserRole
            from app.seed.config import SeedResult
            from app.seed.users import seed_admin

            assert engine.dialect.name == "postgresql"
            assert verify_password("bootstrap-smoke-test", hash_password("bootstrap-smoke-test"))
            print("Bootstrap runtime smoke test passed.")
            return 0
        if sys.argv[1:]:
            print("Unsupported arguments.", file=sys.stderr)
            return 1
        created = bootstrap(SessionLocal)
    except (KeyboardInterrupt, EOFError, getpass.GetPassWarning):
        print("Bootstrap cancelled: secure password input is required.", file=sys.stderr)
        return 1
    except ValueError as exc:
        # Only the controlled validation messages above may be displayed.
        # Other exceptions can contain connection strings or SQL parameters.
        if str(exc) in {
            "Password must not be blank.",
            "Passwords do not match.",
            "Username admin is already occupied. Nothing changed.",
        }:
            print(str(exc), file=sys.stderr)
        else:
            print("Bootstrap failed. Check server configuration.", file=sys.stderr)
        return 1
    except Exception:
        print("Bootstrap failed. Check DATABASE_URL and database availability.", file=sys.stderr)
        return 1
    print("Admin created successfully. Username: admin" if created else "An ADMIN already exists. Nothing changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
