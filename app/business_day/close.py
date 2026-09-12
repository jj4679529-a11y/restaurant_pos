"""Close the completed business day and enqueue its daily Telegram report."""

from app.database.connection import SessionLocal
from app.services.business_day_service import close_previous_business_day


def main() -> None:
    session = SessionLocal()
    try:
        result = close_previous_business_day(session)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    if result.report_created:
        print(f"Closed business day {result.previous_day.business_date}; daily report queued.")
    elif result.previous_day is None:
        print(f"No prior business day exists; current business day {result.current_day.business_date} is open.")
    else:
        print(f"Business day {result.previous_day.business_date} was already closed; no report was queued.")


if __name__ == "__main__":
    main()
