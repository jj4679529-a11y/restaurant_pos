from typing import Protocol
import logging
import re

import httpx


class TelegramClientError(Exception):
    """A retryable configuration, network, or Telegram API delivery error."""

    def __init__(self, message, retry_after=0):
        super().__init__(message)
        self.retry_after = retry_after


class RedactTelegramURL(logging.Filter):
    def filter(self, record):
        record.msg = re.sub(r'(https?://api\.telegram\.org/bot)[^/\s"\']+', r'\1<redacted>', record.getMessage())
        record.args = ()
        return True


for logger_name in ('httpx', 'httpcore', 'httpcore.http11', 'httpcore.connection'):
    logging.getLogger(logger_name).addFilter(RedactTelegramURL())


BOT_COMMANDS = [
    {"command": "boshlash", "description": "Botni ishga tushirish"},
    {"command": "yordam", "description": "Barcha buyruqlar ro'yxati"},
    {"command": "holat", "description": "Server va Telegram holati"},
    {"command": "bugun", "description": "Bugungi umumiy hisobot"},
    {"command": "kunlik", "description": "Joriy kun hisoboti"},
    {"command": "haftalik", "description": "Joriy hafta hisoboti"},
    {"command": "oylik", "description": "Joriy oy hisoboti"},
    {"command": "buyurtmalar", "description": "Oxirgi buyurtmalar"},
    {"command": "kutilayotgan", "description": "Kutilayotgan buyurtmalar"},
    {"command": "bekor", "description": "Bekor qilingan buyurtmalar"},
    {"command": "yetkazish", "description": "Yetkazib berish hisoboti"},
    {"command": "yetkazuvchilar", "description": "Yetkazib beruvchilar hisoboti"},
    {"command": "kassirlar", "description": "Kassirlar bo'yicha savdo"},
    {"command": "topmahsulotlar", "description": "Eng ko'p sotilgan mahsulotlar"},
]


class TelegramClient(Protocol):
    def send_message(self, chat_id: str, text: str) -> None: ...

    def set_commands(self) -> None: ...


class TelegramBotClient:
    """Small synchronous adapter for the Telegram Bot API.

    Error messages deliberately omit the request URL and bot token.
    """

    def __init__(self, bot_token: str | None, timeout_seconds: float = 10.0) -> None:
        self._bot_token = bot_token.strip() if bot_token else ""
        self._timeout_seconds = timeout_seconds

    def send_message(self, chat_id: str, text: str) -> None:
        if not self._bot_token or not chat_id.strip():
            raise TelegramClientError("Telegram is not configured")
        # One outbox row corresponds to one Telegram message, avoiding partial
        # multi-part delivery on retries. Long reports retain totals at the top.
        if len(text.encode('utf-16-le')) // 2 > 4000:
            text = text.encode('utf-16-le')[:7800].decode('utf-16-le', errors='ignore') + '\n… Hisobot qisqartirildi.'
        self._request("sendMessage", {"chat_id": chat_id, "text": text})

    def set_commands(self) -> None:
        self._request(
            "setMyCommands",
            {"commands": BOT_COMMANDS},
        )

    def get_updates(self, offset: int) -> list[dict]:
        payload = self._request("getUpdates", {"offset": offset, "timeout": 0, "limit": 50, "allowed_updates": ["message"]})
        updates = payload.get('result')
        if not isinstance(updates, list):
            raise TelegramClientError("Telegram API returned an invalid response")
        return updates

    def _request(self, method: str, data: dict) -> dict:
        if not self._bot_token:
            raise TelegramClientError("Telegram is not configured")
        try:
            with httpx.Client(timeout=self._timeout_seconds) as client:
                response = client.post(
                    f"https://api.telegram.org/bot{self._bot_token}/{method}",
                    json=data,
                )
        except httpx.TimeoutException as exc:
            raise TelegramClientError("Telegram request timed out") from exc
        except httpx.RequestError as exc:
            raise TelegramClientError("Telegram network request failed") from exc
        try:
            payload = response.json()
            if response.status_code < 200 or response.status_code >= 300 or not isinstance(payload, dict) or payload.get("ok") is not True:
                delay = payload.get('parameters', {}).get('retry_after', 0) if isinstance(payload, dict) else 0
                raise TelegramClientError("Telegram API rejected the message", delay if isinstance(delay, int) else 0)
            return payload
        except ValueError as exc:
            raise TelegramClientError("Telegram API returned an invalid response") from exc
