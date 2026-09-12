# Restaurant POS

Existing restaurant point-of-sale application with a FastAPI/PostgreSQL backend,
PySide6 touchscreen cashier UI, and a separate administrator UI.

## Stack and setup

Python 3.12, PostgreSQL 14, SQLAlchemy 2.x, Alembic, Pydantic v2,
PySide6, and pytest. Run commands from the project root.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows, activate with `.venv\Scripts\Activate.ps1` in PowerShell.
Create a PostgreSQL database and database user. Copy `.env.example` to `.env`
only if `.env` does not already exist. Set your local database credentials,
a strong random JWT secret, and an administrator bootstrap password.
Never use the example placeholders for a running installation.

```bash
alembic upgrade head
```

For an initial installation, configure actual menu prices as documented in
[the menu guide](docs/cashier-final-menu.md), then run the idempotent seed:

```bash
python -m app.seed.seed_database
```

Do not overwrite an existing installation's `.env` or database.

## Run locally

Backend (binding all interfaces makes it reachable on the local network;
use `127.0.0.1` instead for localhost-only development):

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

In separate activated terminals:

```bash
python pos.py
python admin.py
```

Desktop clients communicate only through authenticated HTTP API calls.
For a separate terminal, configure only `POS_API_BASE_URL`, `POS_PRINTER_ID`,
and optionally `POS_API_TIMEOUT_SECONDS`; never copy backend database or JWT
secrets to desktop terminals. Access tokens are kept in application memory.
Admin login requires the ADMIN role.

Printer IDs are configured per terminal, never hardcoded. Physical printer
transport still requires deployment configuration/implementation; do not assume
a saved payment means a physical receipt was printed. Payment remains final
if printing fails.

## Verification

Tests require PostgreSQL and a configured `DATABASE_URL`. Use a dedicated test
database with migrations applied; some concurrency tests commit temporary rows.

```bash
env -u DEBUG pytest -q
alembic check
```

## Data and security

`.env`, `.env.*` (except the safe example), virtual environments, database dumps,
and runtime uploads under `media/` are excluded from Git. Product images default
to `media/products`, with relative references served through the authenticated
API. Keep separate secure database and upload backups: this Git repository is
a source-code backup, not a restaurant-data backup. If `PRODUCT_MEDIA_DIR` is
customized, keep that runtime directory outside tracked source as well.

Osh prices come from configured PriceOptions. Go'sht is only a manually priced
AddOn, never a Product or PriceOption.

See [the Admin UI guide](docs/admin-panel.md) for catalog configuration.
Phase 13 plans two terminals using one HTTP backend and PostgreSQL server;
networking, firewall changes, Windows installers, and real printer deployment
are not part of this baseline backup.

For Phase 13.1 Windows setup and the pending physical acceptance checklist, see
[two-monoblock Wi-Fi setup](docs/two-monoblock-wifi.md).
