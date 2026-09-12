from typing import Protocol

import httpx


class TelegramClientError(Exception):
    """A retryable configuration, network, or Telegram API delivery error."""


class TelegramClient(Protocol):
    def send_message(self, chat_id: str, text: str) -> None: ...


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
        try:
            with httpx.Client(timeout=self._timeout_seconds) as client:
                response = client.post(
                    f"https://api.telegram.org/bot{self._bot_token}/sendMessage",
                    json={"chat_id": chat_id, "text": text},
                )
        except httpx.TimeoutException as exc:
            raise TelegramClientError("Telegram request timed out") from exc
        except httpx.RequestError as exc:
            raise TelegramClientError("Telegram network request failed") from exc
        if response.status_code < 200 or response.status_code >= 300:
            raise TelegramClientError(f"Telegram API returned HTTP {response.status_code}")
        try:
            payload = response.json()
            if not isinstance(payload, dict) or payload.get("ok") is not True:
                raise TelegramClientError("Telegram API rejected the message")
        except ValueError as exc:
            raise TelegramClientError("Telegram API returned an invalid response") from exc
