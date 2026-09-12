from app.core.config import get_settings
from app.database.connection import SessionLocal
from app.services.telegram_outbox_service import process_pending_messages
from app.telegram.client import TelegramBotClient


def run_once() -> None:
    settings = get_settings()
    result = process_pending_messages(
        SessionLocal,
        TelegramBotClient(settings.TELEGRAM_BOT_TOKEN),
        settings.TELEGRAM_CHAT_ID,
        settings.TELEGRAM_OUTBOX_BATCH_SIZE,
    )
    print(f"Telegram outbox: attempted={result.attempted} sent={result.sent} failed={result.failed}")


if __name__ == "__main__":
    run_once()
