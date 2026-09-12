from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from time import sleep
from uuid import uuid4

from sqlalchemy import delete, select

from app.database.connection import SessionLocal
from app.models import TelegramMessageType, TelegramOutbox, TelegramOutboxStatus
from app.services.telegram_outbox_service import process_outbox_message, process_pending_messages
from app.telegram.client import TelegramBotClient, TelegramClientError


class FakeTelegramClient:
    def __init__(self, outcomes: list[Exception | None] | None = None, delay: float = 0) -> None:
        self.outcomes = outcomes or []
        self.delay = delay
        self.sent: list[tuple[str, str]] = []

    def send_message(self, chat_id: str, text: str) -> None:
        if self.delay:
            sleep(self.delay)
        outcome = self.outcomes.pop(0) if self.outcomes else None
        if outcome:
            raise outcome
        self.sent.append((chat_id, text))


def _messages(count: int = 1) -> list[int]:
    session = SessionLocal()
    try:
        prefix = uuid4().hex
        rows = [
            TelegramOutbox(
                message_type=TelegramMessageType.PAID_ORDER,
                order_id=None,
                message_text=f"telegram-test-{prefix}-{index}",
                status=TelegramOutboxStatus.PENDING,
                attempts=0,
                created_at=datetime(1970, 1, 1, tzinfo=UTC) + timedelta(seconds=index),
            )
            for index in range(count)
        ]
        session.add_all(rows)
        session.commit()
        return [row.id for row in rows]
    finally:
        session.close()


def _cleanup(message_ids: list[int]) -> None:
    session = SessionLocal()
    try:
        session.execute(delete(TelegramOutbox).where(TelegramOutbox.id.in_(message_ids)))
        session.commit()
    finally:
        session.close()


def test_pending_message_sends_once_and_becomes_sent() -> None:
    message_id = _messages()[0]
    client = FakeTelegramClient()
    try:
        first = process_pending_messages(SessionLocal, client, "chat-id", batch_size=1)
        second = process_outbox_message(SessionLocal, message_id, client, "chat-id")
        session = SessionLocal()
        try:
            message = session.get(TelegramOutbox, message_id)
            assert first.attempted == first.sent == 1
            assert second.attempted is False
            assert message.status is TelegramOutboxStatus.SENT
            assert message.sent_at is not None
            assert message.attempts == 1
            assert message.last_error is None
            assert len(client.sent) == 1
        finally:
            session.close()
    finally:
        _cleanup([message_id])


def test_failure_is_retryable_and_missing_config_fails_safely() -> None:
    message_id = _messages()[0]
    client = FakeTelegramClient([TelegramClientError("network offline"), None])
    try:
        failed = process_outbox_message(SessionLocal, message_id, client, "chat-id")
        retried = process_outbox_message(SessionLocal, message_id, client, "chat-id")
        session = SessionLocal()
        try:
            message = session.get(TelegramOutbox, message_id)
            assert failed.status is TelegramOutboxStatus.ERROR
            assert retried.status is TelegramOutboxStatus.SENT
            assert message.attempts == 2
            assert message.last_error is None
        finally:
            session.close()

        config_message = _messages()[0]
        result = process_outbox_message(SessionLocal, config_message, TelegramBotClient(None), None)
        session = SessionLocal()
        try:
            stored = session.get(TelegramOutbox, config_message)
            assert result.status is TelegramOutboxStatus.ERROR
            assert stored.status is TelegramOutboxStatus.ERROR
            assert stored.attempts == 1
            assert stored.last_error == "Telegram is not configured"
        finally:
            session.close()
        _cleanup([config_message])
    finally:
        _cleanup([message_id])


def test_batch_is_oldest_first_and_respects_limit() -> None:
    message_ids = _messages(2)
    client = FakeTelegramClient()
    try:
        result = process_pending_messages(SessionLocal, client, "chat-id", batch_size=1)
        assert result.attempted == 1
        assert [text for _chat, text in client.sent] == [
            session_text for session_text in _message_texts(message_ids[:1])
        ]
        session = SessionLocal()
        try:
            states = [session.get(TelegramOutbox, message_id).status for message_id in message_ids]
            assert states == [TelegramOutboxStatus.SENT, TelegramOutboxStatus.PENDING]
        finally:
            session.close()
    finally:
        _cleanup(message_ids)


def _message_texts(message_ids: list[int]) -> list[str]:
    session = SessionLocal()
    try:
        return list(session.scalars(
            select(TelegramOutbox.message_text)
            .where(TelegramOutbox.id.in_(message_ids))
            .order_by(TelegramOutbox.id)
        ))
    finally:
        session.close()


def test_concurrent_workers_claim_one_message_once() -> None:
    message_id = _messages()[0]
    client = FakeTelegramClient(delay=0.2)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(
                lambda _index: process_outbox_message(SessionLocal, message_id, client, "chat-id"),
                range(2),
            ))
        assert sum(result.attempted for result in results) == 1
        assert len(client.sent) == 1
    finally:
        _cleanup([message_id])
