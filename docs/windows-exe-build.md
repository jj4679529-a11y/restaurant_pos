# Windows Executable Build Guide

## Overview

Three executable artifacts are built for Windows deployment using PyInstaller
on GitHub Actions (`windows-latest`, Python 3.12):

| Executable | Entry Point | Console | Purpose |
|---|---|---|---|
| `RestaurantPOS.exe` | `pos.py` | No | PySide6 cashier UI (API client only) |
| `RestaurantAdmin.exe` | `admin.py` | No | PySide6 admin UI (API client only) |
| `RestaurantServer.exe` | `server.py` | Yes | FastAPI/Uvicorn backend for Monoblock 1 |

## Build Requirements

- Python 3.12 x64
- `requirements.txt` (includes PySide6-Essentials, FastAPI, Uvicorn, etc.)
- PyInstaller (`pip install pyinstaller`)

## Build Process

### Automated (GitHub Actions)

Pushing to `phase-13-two-monoblock` triggers `build-windows.yml`:

1. Sets up Python 3.12 on `windows-latest`
2. Installs `requirements.txt`
3. Installs PyInstaller
4. Runs full test suite (`env -u DEBUG pytest -q`)
5. Runs `alembic check`
6. Builds all three executables from their spec files
7. Uploads executables as a build artifact

### Manual (Local Windows)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install pyinstaller

$env:DEBUG = $null
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean pos.spec
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean admin.spec
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean server.spec
```

Executables are placed in `dist/`.

## Runtime .env Strategy

**.env is NOT bundled** in any executable. Each executable reads configuration
from environment variables or from a `.env` file located next to the executable.

### RestaurantPOS.exe and RestaurantAdmin.exe

These are API clients. They need only POS terminal settings:

```dotenv
POS_API_BASE_URL=http://127.0.0.1:8000
POS_PRINTER_ID=
POS_API_TIMEOUT_SECONDS=10
```

No database URL, JWT secret, Telegram token, or other backend secrets are needed.

### RestaurantServer.exe

The FastAPI backend requires all server settings:

```dotenv
DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@localhost:5432/restaurant_pos
APP_NAME="Restaurant POS"
APP_ENV=development
DEBUG=false
JWT_SECRET_KEY=...
ADMIN_USERNAME=admin
ADMIN_PASSWORD=...
POS_API_BASE_URL=http://127.0.0.1:8000
POS_PRINTER_ID=
```

### Configuration Precedence

1. Environment variables (highest priority)
2. `.env` file in the executable's directory
3. Default values defined in source code (lowest priority)

## Executable Details

### RestaurantPOS.exe

- PySide6 cashier UI
- No console window (`console=False`)
- API client only — communicates with RestaurantServer.exe via HTTP
- Configurable `POS_API_BASE_URL`, `POS_PRINTER_ID`, `POS_API_TIMEOUT_SECONDS`

### RestaurantAdmin.exe

- PySide6 admin UI
- No console window (`console=False`)
- API client only — communicates with RestaurantServer.exe via HTTP
- Requires ADMIN role credentials for login

### RestaurantServer.exe

- FastAPI/Uvicorn backend
- Console window enabled (for logging)
- Configurable host and port via `DATABASE_URL`/environment
- Supports `0.0.0.0:8000` binding
- PostgreSQL is NOT bundled — must be installed separately on Monoblock 1

## Deployment Notes

- Each Monoblock gets its own `.env` and executable(s)
- Monoblock 1 runs `RestaurantServer.exe` (with PostgreSQL) and can also run `RestaurantPOS.exe`
- Monoblock 2 runs only `RestaurantPOS.exe` or `RestaurantAdmin.exe` (no PostgreSQL, no server)
- Physical printer configuration is done server-side via Printer records; executables only reference printer IDs
