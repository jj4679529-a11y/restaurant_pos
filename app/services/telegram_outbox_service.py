from dataclasses import dataclass
from datetime import datetime
from typing import Callable
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import TelegramOutbox, TelegramOutboxStatus
from app.telegram.client import TelegramClient, TelegramClientError

TASHKENT = ZoneInfo("Asia/Tashkent")
SessionFactory = Callable[[], Session]
OUTBOX_LOCK_NAMESPACE = 7_001


@dataclass(frozen=True)
class OutboxProcessResult:
    message_id: int
    status: TelegramOutboxStatus | None
    attempted: bool


@dataclass(frozen=True)
class OutboxBatchResult:
    attempted: int
    sent: int
    failed: int
    skipped: int


def _eligible_ids(session: Session, batch_size: int) -> list[int]:
    return list(session.scalars(
        select(TelegramOutbox.id)
        .where(TelegramOutbox.status.in_((TelegramOutboxStatus.PENDING, TelegramOutboxStatus.ERROR)))
        .order_by(TelegramOutbox.created_at, TelegramOutbox.id)
        .limit(batch_size)
    ))


def _try_advisory_lock(session: Session, message_id: int) -> bool:
    return bool(session.scalar(select(func.pg_try_advisory_lock(OUTBOX_LOCK_NAMESPACE, message_id))))


def _release_advisory_lock(session: Session, message_id: int) -> None:
    session.scalar(select(func.pg_advisory_unlock(OUTBOX_LOCK_NAMESPACE, message_id)))
    session.commit()


def _safe_error(error: TelegramClientError) -> str:
    return str(error)[:500] or "Telegram delivery failed"


def process_outbox_message(
    session_factory: SessionFactory,
    message_id: int,
    client: TelegramClient,
    chat_id: str | None,
) -> OutboxProcessResult:
    """Attempt one message once, using a PostgreSQL advisory claim lock."""
    session = session_factory()
    acquired = False
    try:
        acquired = _try_advisory_lock(session, message_id)
        if not acquired:
            session.rollback()
            return OutboxProcessResult(message_id, None, attempted=False)

        message = session.scalars(
            select(TelegramOutbox).where(TelegramOutbox.id == message_id).with_for_update()
        ).one_or_none()
        if message is None or message.status is TelegramOutboxStatus.SENT:
            session.commit()
            return OutboxProcessResult(message_id, message.status if message else None, attempted=False)

        # The advisory lock survives this commit; release the row lock before
        # the potentially slow HTTPS call.
        text = message.message_text
        session.commit()
        try:
            client.send_message(chat_id or "", text)
        except TelegramClientError as error:
            message = session.scalars(
                select(TelegramOutbox).where(TelegramOutbox.id == message_id).with_for_update()
            ).one()
            message.status = TelegramOutboxStatus.ERROR
            message.attempts += 1
            message.last_error = _safe_error(error)
            session.commit()
            return OutboxProcessResult(message_id, TelegramOutboxStatus.ERROR, attempted=True)

        message = session.scalars(
            select(TelegramOutbox).where(TelegramOutbox.id == message_id).with_for_update()
        ).one()
        message.status = TelegramOutboxStatus.SENT
        message.attempts += 1
        message.sent_at = datetime.now(TASHKENT)
        message.last_error = None
        session.commit()
        return OutboxProcessResult(message_id, TelegramOutboxStatus.SENT, attempted=True)
    finally:
        if acquired:
            try:
                _release_advisory_lock(session, message_id)
            finally:
                session.close()
        else:
            session.close()


def process_pending_messages(
    session_factory: SessionFactory,
    client: TelegramClient,
    chat_id: str | None,
    batch_size: int = 50,
) -> OutboxBatchResult:
    """Process a deterministic, bounded snapshot of pending/retryable rows."""
    session = session_factory()
    try:
        message_ids = _eligible_ids(session, batch_size)
    finally:
        session.close()

    results = [process_outbox_message(session_factory, message_id, client, chat_id) for message_id in message_ids]
    return OutboxBatchResult(
        attempted=sum(result.attempted for result in results),
        sent=sum(result.status is TelegramOutboxStatus.SENT for result in results),
        failed=sum(result.status is TelegramOutboxStatus.ERROR and result.attempted for result in results),
        skipped=sum(not result.attempted for result in results),
    )
