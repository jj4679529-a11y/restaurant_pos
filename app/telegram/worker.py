from app.core.config import get_settings
from app.database.connection import SessionLocal
from app.services.telegram_outbox_service import process_pending_messages
from app.telegram.client import TelegramBotClient
from app.telegram.runtime import admin_chat_id, valid_configuration


def run_once() -> None:
    settings = get_settings()
    if not settings.TELEGRAM_ENABLED or not valid_configuration(settings):
        print('Telegram disabled or not configured')
        return
    result = process_pending_messages(
        SessionLocal,
        TelegramBotClient(settings.TELEGRAM_BOT_TOKEN),
        admin_chat_id(settings),
        settings.TELEGRAM_OUTBOX_BATCH_SIZE,
    )
    print(f"Telegram outbox: attempted={result.attempted} sent={result.sent} failed={result.failed}")


if __name__ == "__main__":
    run_once()
