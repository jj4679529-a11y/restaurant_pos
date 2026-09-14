from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, or_
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
        .where(or_(TelegramOutbox.next_attempt_at.is_(None), TelegramOutbox.next_attempt_at <= datetime.now(TASHKENT)))
        .order_by(TelegramOutbox.created_at, TelegramOutbox.id)
        .limit(batch_size)
    ))


def _try_advisory_lock(session: Session, message_id: int) -> bool:
    return bool(session.scalar(select(func.pg_try_advisory_lock(OUTBOX_LOCK_NAMESPACE, message_id))))


def _release_advisory_lock(session: Session, message_id: int) -> None:
    session.scalar(select(func.pg_advisory_unlock(OUTBOX_LOCK_NAMESPACE, message_id)))
    session.commit()


def _safe_error(error: TelegramClientError) -> str:
    allowed = {"Telegram is not configured", "Telegram request timed out", "Telegram network request failed",
               "Telegram API rejected the message", "Telegram API returned an invalid response"}
    return str(error) if str(error) in allowed else "Telegram delivery failed"


def process_outbox_message(
    session_factory: SessionFactory,
    message_id: int,
    client: TelegramClient,
    chat_id: str | None,
    *,
    respect_backoff: bool = False,
) -> OutboxProcessResult:
    """Attempt one message once, using a PostgreSQL advisory claim lock."""
    # A session-owned connection can return to the pool on commit. Pin one
    # physical connection so the session advisory lock survives HTTPS/commits.
    factory_session = session_factory()
    try:
        connection = factory_session.get_bind().connect()
    finally:
        factory_session.close()
    session = Session(bind=connection)
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
        if respect_backoff and message.next_attempt_at and message.next_attempt_at > datetime.now(TASHKENT):
            session.commit()
            return OutboxProcessResult(message_id, None, attempted=False)

        # The advisory lock survives this commit; release the row lock before
        # the potentially slow HTTPS call.
        text = message.message_text
        session.commit()
        try:
            client.send_message(chat_id or "", text)
        except Exception as error:
            message = session.scalars(
                select(TelegramOutbox).where(TelegramOutbox.id == message_id).with_for_update()
            ).one()
            message.status = TelegramOutboxStatus.ERROR
            message.attempts += 1
            message.last_error = _safe_error(error)
            delay = min(3600, 5 * 2 ** min(message.attempts - 1, 10))
            delay = max(delay, min(86400, getattr(error, "retry_after", 0)))
            message.next_attempt_at = datetime.now(TASHKENT) + timedelta(seconds=delay)
            session.commit()
            return OutboxProcessResult(message_id, TelegramOutboxStatus.ERROR, attempted=True)

        message = session.scalars(
            select(TelegramOutbox).where(TelegramOutbox.id == message_id).with_for_update()
        ).one()
        message.status = TelegramOutboxStatus.SENT
        message.attempts += 1
        message.sent_at = datetime.now(TASHKENT)
        message.last_error = None
        message.next_attempt_at = None
        session.commit()
        return OutboxProcessResult(message_id, TelegramOutboxStatus.SENT, attempted=True)
    finally:
        try:
            if acquired:
                session.rollback()
                _release_advisory_lock(session, message_id)
        except Exception:
            connection.invalidate()  # Never return a still-locked connection to the pool.
            raise
        finally:
            session.close()
            connection.close()


def process_pending_messages(
    session_factory: SessionFactory,
    client: TelegramClient,
    chat_id: str | None,
    batch_size: int = 50,
    stop_requested: Callable[[], bool] = lambda: False,
) -> OutboxBatchResult:
    """Process a deterministic, bounded snapshot of pending/retryable rows."""
    session = session_factory()
    try:
        message_ids = _eligible_ids(session, batch_size)
    finally:
        session.close()

    results = []
    for message_id in message_ids:
        if stop_requested():
            break
        results.append(process_outbox_message(session_factory, message_id, client, chat_id, respect_backoff=True))
    return OutboxBatchResult(
        attempted=sum(result.attempted for result in results),
        sent=sum(result.status is TelegramOutboxStatus.SENT for result in results),
        failed=sum(result.status is TelegramOutboxStatus.ERROR and result.attempted for result in results),
        skipped=sum(not result.attempted for result in results),
    )
