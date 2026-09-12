from app.database.connection import SessionLocal
from app.seed.config import SeedSettings
from app.seed.runner import seed_all


def main() -> None:
    settings = SeedSettings()
    session = SessionLocal()
    try:
        result = seed_all(session, settings)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    for message in result.messages:
        print(message)
    print("Seed completed")


if __name__ == "__main__":
    main()
