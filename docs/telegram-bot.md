# Telegram Bot Integration

## BotFather Setup

1. Open Telegram and search for `@BotFather`
2. Send `/newbot`
3. Choose a name (e.g., `Restaurant POS Bot`)
4. Choose a username (must end with `bot`, e.g., `restaurant_pos_bot`)
5. Copy the **Bot Token** (format: `123456789:ABCdefGhIJKlmNoPQRstuVWxYz`)

## How to Obtain Chat ID

Send any message to your bot (e.g., "hello"). Then visit:

```
https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
```

Find your message in the `result` array. The `chat.id` field is your Chat ID (a number like `123456789`).

For private bots, the Chat ID is a negative number (e.g., `-1001234567890` for groups) or a positive number for private chats.

## Required .env Variables

```dotenv
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRstuVWxYz
TELEGRAM_ADMIN_CHAT_ID=123456789
TELEGRAM_ENABLED=false
TELEGRAM_DAILY_REPORT_TIME=23:00
TELEGRAM_OUTBOX_BATCH_SIZE=50
```

### Variable Descriptions

| Variable | Required | Default | Description |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Yes | — | Bot token from BotFather |
| `TELEGRAM_ADMIN_CHAT_ID` | Yes | — | Chat ID that can send commands. Must match a valid Telegram chat ID (numeric, max 19 digits) |
| `TELEGRAM_ENABLED` | No | `false` | Set `true` to enable Telegram notifications |
| `TELEGRAM_DAILY_REPORT_TIME` | No | — | Time (HH:MM, Tashkent) to send daily sales report |
| `TELEGRAM_OUTBOX_BATCH_SIZE` | No | `50` | Max messages processed per worker cycle |

## How to Enable/Disable Telegram

Set `TELEGRAM_ENABLED=true` in your `.env` file and restart RestaurantServer.

If `TELEGRAM_ENABLED=false` or configuration is incomplete (missing token, invalid chat ID), the Telegram worker starts but does nothing. All Telegram calls return "disabled or not configured".

## How to Test Telegram Notifications

1. Set `TELEGRAM_ENABLED=true` with valid token and chat ID
2. Restart RestaurantServer
3. Pay for an order at the POS terminal
4. Check Telegram for the payment notification message

The payment notification includes:
- Order number
- Cashier name
- Order type (Choyxona / Yetkazib berish)
- Total amount in so'm
- Time of payment

### Bot Commands (Admin Only)

Only the configured `TELEGRAM_ADMIN_CHAT_ID` can send commands:

- `/start` — Show available commands
- `/status` — Backend status, current business day, pending Telegram messages
- `/today` — Today's sales summary
- `/delivery` — Delivery worker totals for current day

### Notification Types

| Event | Message |
|---|---|
| Payment completed | ✅ TO'LOV QABUL QILINDI |
| Printer failure after payment | ⚠️ CHEK CHIQMADI |
| Delivery order assigned | 🚚 YETKAZIB BERISH TAYINLANDI |
| Daily report (scheduled) | 📊 KUNLIK HISOBOT |

## Security Notes

- Bot token is never logged or exposed in error messages
- Chat ID is validated before processing commands
- Telegram API URL redaction in logs (bot token replaced with `<redacted>`)
- Unauthorized chat IDs are silently rejected (no response sent)
