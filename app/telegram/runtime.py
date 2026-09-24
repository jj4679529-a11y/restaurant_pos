"""Server-managed singleton worker. Network failures never enter POS requests."""
import logging
import re
from threading import Event, Thread

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Setting, TelegramMessageType
from app.services.telegram_outbox_service import process_pending_messages
from app.telegram.client import TelegramBotClient
from app.telegram.events import collect_committed_events, command_reply, enqueue, schedule_report

log = logging.getLogger(__name__)
LEADER_NAMESPACE = 7002
OFFSET_KEY = '_telegram_update_offset'


def admin_chat_id(settings):
    value = settings.TELEGRAM_ADMIN_CHAT_ID or settings.TELEGRAM_CHAT_ID or ''
    return value.strip()


def valid_configuration(settings):
    chat_id = admin_chat_id(settings)
    return (bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_BOT_TOKEN.strip())
            and bool(re.fullmatch(r'-?[1-9][0-9]{0,18}', chat_id))
            and abs(int(chat_id)) < 2**63
            and (not settings.TELEGRAM_DAILY_REPORT_TIME or bool(re.fullmatch(
                r'(?:[01][0-9]|2[0-3]):[0-5][0-9]', settings.TELEGRAM_DAILY_REPORT_TIME))))


def handle_update(session, update, configured_chat_id):
    message = update.get('message', {})
    chat = message.get('chat', {})
    # Group chats are intentionally excluded: a configured group does not make
    # every member an administrator. Use the administrator's private chat ID.
    if str(chat.get('id')) != configured_chat_id or chat.get('type') != 'private':
        return False
    text = message.get('text', '')
    if not isinstance(text, str) or not text.startswith('/'):
        return False
    parts = text.strip().split()
    command = parts[0].split('@')[0].lower()
    args = parts[1:]

    enqueue(
        session,
        f'bot:{configured_chat_id}:{update["update_id"]}',
        TelegramMessageType.BOT_REPLY,
        command_reply(session, command, args=args),
    )
    return True


class TelegramRuntime:
    def __init__(self, session_factory, settings, client=None):
        self.factory = session_factory
        self.settings = settings
        self.client = client or TelegramBotClient(settings.TELEGRAM_BOT_TOKEN, timeout_seconds=5)
        self.stop_event = Event()
        self.thread = None

    def start(self):
        if not self.settings.TELEGRAM_ENABLED:
            return
        if not valid_configuration(self.settings):
            log.warning('Telegram disabled: invalid or missing Telegram configuration')
            return
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = Thread(target=self.run, name='telegram-worker', daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join()  # Bounded HTTP timeouts; cancellation between sends.

    def cycle(self):
        with self.factory.begin() as session:
            collect_committed_events(session, self.settings.TELEGRAM_OUTBOX_BATCH_SIZE)
            schedule_report(session, self.settings.TELEGRAM_DAILY_REPORT_TIME)
        process_pending_messages(self.factory, self.client, admin_chat_id(self.settings),
                                 self.settings.TELEGRAM_OUTBOX_BATCH_SIZE, self.stop_event.is_set)
        if self.stop_event.is_set():
            return
        with self.factory() as session:
            value = session.scalar(select(Setting.value).where(Setting.key == OFFSET_KEY))
            offset = int(value or 0)
        updates = self.client.get_updates(offset)
        for update in updates:
            if self.stop_event.is_set():
                break
            update_id = update.get('update_id')
            if not isinstance(update_id, int) or update_id < offset:
                continue
            with self.factory.begin() as session:
                handle_update(session, update, admin_chat_id(self.settings))
                # Reply and checkpoint commit together, before acknowledging to
                # Telegram via the next getUpdates offset.
                session.execute(insert(Setting).values(key=OFFSET_KEY, value=str(update_id + 1))
                                .on_conflict_do_update(index_elements=['key'], set_={'value': str(update_id + 1)}))
            offset = update_id + 1

    def run(self):
        while not self.stop_event.is_set():
            connection = None
            acquired = False
            try:
                with self.factory() as probe:
                    connection = probe.get_bind().connect()
                acquired = bool(connection.scalar(select(func.pg_try_advisory_lock(LEADER_NAMESPACE, 0))))
                connection.commit()
                if acquired:
                    # Register Telegram slash-command menu once whenever this
                    # server becomes the singleton Telegram leader.
                    try:
                        set_commands = getattr(
                            self.client,
                            "set_commands",
                            None,
                        )
                        if callable(set_commands):
                            set_commands()
                            log.info(
                                "Telegram command menu registered"
                            )
                    except Exception:
                        # Menu registration must never stop POS or reports.
                        log.warning(
                            "Telegram command menu registration failed; "
                            "will continue without blocking the worker"
                        )

                    while not self.stop_event.is_set():
                        # Detect leader connection loss before every cycle.
                        connection.execute(select(1))
                        connection.commit()
                        try:
                            self.cycle()
                        except Exception:
                            log.warning('Telegram cycle failed; will retry (details suppressed)')
                        self.stop_event.wait(5)
            except Exception:
                log.warning('Telegram worker unavailable; will retry (details suppressed)')
            finally:
                if connection is not None:
                    try:
                        if acquired:
                            connection.rollback()
                            connection.execute(select(func.pg_advisory_unlock(LEADER_NAMESPACE, 0)))
                            connection.commit()
                    except Exception:
                        connection.invalidate()
                    finally:
                        connection.close()
            self.stop_event.wait(5)
