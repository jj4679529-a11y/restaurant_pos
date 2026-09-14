# Single-entry Windows desktop

Launch `RestaurantPOS.exe`. It checks `/health` off the GUI thread before showing
cashier login. Existing authentication remains required for the cashier.

## Configuration (beside the executables)

```dotenv
POS_API_BASE_URL=http://127.0.0.1:8000
POS_SERVER_START_TIMEOUT_SECONDS=45
AUTO_START_WITH_WINDOWS=false
```

Keep the existing terminal printer configuration and server configuration. No
secrets are included in the executable or specs. POS never imports database code.

If the endpoint is loopback HTTP on port 8000 and unavailable, POS starts sibling
`RestaurantServer.exe` with its working directory set to the executable directory.
The server uses its existing environment/adjacent `.env`. The local startup lock
serializes POS launchers; the supporting Windows server additionally holds a named
mutex for its lifetime, preventing duplicate automatically/manually started server
processes. Rebuild the server too to include this protection. POS does not stop the
server on exit because other terminals may be using it.

Remote endpoints are never auto-started. POS2 should point to POS1's Wi-Fi address;
it needs no PostgreSQL credentials. Failure/timeout gives a retry screen, not a
frozen window. `/health` indicates HTTP readiness, not PostgreSQL readiness.

## Admin access

The Admin button opens a fresh username/password dialog using the existing login
API and verifies `/api/users?limit=1` under backend permissions. The temporary
Admin client uses the same HTTP implementation and URL but a separate token, so
cashier identity and cart cannot be elevated accidentally. Returning with
`← Kassaga qaytish` or closing the Admin window clears the Admin session, restores
the cashier/cart, and reloads the catalog. RestaurantAdmin.exe remains optional
for backward compatibility; cashiers do not need to launch it.

## Windows login auto-start

Opt in with `AUTO_START_WITH_WINDOWS=true`, then launch the packaged POS once.
It sets only the current user's `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`
value named `RestaurantPOS` to the quoted executable path. No administrator rights
or password storage are required. Set false and launch once to remove that value.
This starts on user login, not before Windows login. Source-mode and non-Windows
execution do not register auto-start. A registration failure is shown explicitly.

## UX and scope

The cashier uses a roughly 70/30 catalog/cart splitter, horizontal scrollable
categories, touch product cards, existing item controls and payment/printing state
machine. Category/product/image loading runs in background; first active category
is selected, and empty/error/retry states are explicit. Shared QSS lives in
`app/ui/styles.py` and is bundled as Python module data without external assets.

Backend gaps are intentionally not hidden: takeaway is disabled because OrderType
only supports CHAYKHANA/DELIVERY. No tables/rooms APIs or existing Admin pages for
them exist. Existing Admin resources and dashboard are retained; order history
remains accessible in the cashier's Saved Orders. No discount logic was added.

## Build on Windows (Python 3.12)

```powershell
python -m pip install -r requirements.txt
python -m pip install pyinstaller
python -m PyInstaller --noconfirm --clean pos.spec
python -m PyInstaller --noconfirm --clean server.spec
```

Place both executables from `dist` together. The existing Windows Actions workflow
builds them and uploads `windows-executables`. Do not bundle `.env` or credentials.

Windows physical acceptance still needs verification: local and remote health,
simultaneous starts, startup failure, registry enable/disable, Admin return with a
draft cart, and the target touchscreen resolutions. No backend/business/schema
changes are required for this desktop work.
