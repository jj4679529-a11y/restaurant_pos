# Phase 13.1 — two Windows monoblocks on local Wi-Fi

Software verification is not physical deployment acceptance. Complete the checklist
below on both actual Windows machines before using the installation operationally.

POS1 hosts PostgreSQL, FastAPI and the cashier UI. POS2 runs only the HTTP cashier
client. Both use one backend/database; there is no local offline order queue.
Internet is not needed during core operation. Initial dependency installation
requires internet or previously prepared installation media.

## Monoblock 1 (server + POS)

Install Python 3.12 x64, PostgreSQL 14, and a copy of this project. In PowerShell,
from the project root (do not copy a Mac virtual environment):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Create the local PostgreSQL database/user. Keep PostgreSQL listening on localhost;
do not open TCP 5432 or change pg_hba.conf to allow POS2. If this is an existing
installation, preserve its database and .env. For a fresh setup copy .env.example
to .env and privately configure DATABASE_URL, JWT_SECRET_KEY and ADMIN_PASSWORD.
Use a strong random JWT secret and bootstrap password; never retain placeholders.
Configure actual menu prices before seeding (see cashier-final-menu.md).

```powershell
Remove-Item Env:DEBUG -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.seed.seed_database
.\.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Alternatively run `./scripts/start_server_windows.ps1`. It starts only FastAPI;
it does not change firewall, database, passwords or system execution policy.
In a separate PowerShell terminal run `.\.venv\Scripts\python.exe pos.py`.
With the environment activated, the equivalent command is `python pos.py`.
Run `python admin.py` with ADMIN credentials for central catalog administration.

POS1's local .env must contain:

```dotenv
POS_API_BASE_URL=http://127.0.0.1:8000
POS_PRINTER_ID=
```

Set POS_PRINTER_ID to Printer 1's actual numeric database record ID once configured.
Blank means unconfigured, not a fallback to an arbitrary printer.

## Wi-Fi and firewall

Connect both PCs to the same trusted router/SSID and subnet. Disable AP/client
isolation for this trusted network; do not use an isolated guest SSID. Keep strong
Wi-Fi access controls: HTTP does not encrypt credentials or bearer tokens on the LAN.
Do not forward port 8000 from the internet, disable authentication, or disable the firewall.

Run `ipconfig` on POS1 and use the Wi-Fi adapter's IPv4 (not a VPN/virtual adapter).
Use a DHCP reservation later so this address remains stable. No source IP is hardcoded.
Check `Get-NetConnectionProfile`. Only on the trusted restaurant network, set that
adapter's profile to Private in Windows Settings > Network & Internet > Wi-Fi >
connected network > Network profile type.

In Administrator PowerShell on POS1, create a named private/local-subnet rule:

```powershell
New-NetFirewallRule -Name RestaurantPOS-API -DisplayName 'Restaurant POS API' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8000 -Profile Private -RemoteAddress LocalSubnet
Get-NetFirewallRule -Name RestaurantPOS-API
```

Do not add duplicate rules on repeated setup. For stricter two-terminal access,
replace LocalSubnet with POS2's reserved IPv4 address. To undo only this rule:
`Remove-NetFirewallRule -Name RestaurantPOS-API`.
No inbound API or PostgreSQL firewall rule is needed on POS2.

## Monoblock 2 (client only)

Install Python 3.12 x64 and copy the project source, never POS1's .env or .venv.
Create a new venv and install requirements.txt with the same commands above.
The shared requirements include backend libraries, but no PostgreSQL server,
DATABASE_URL, migration, seed, JWT secret or Telegram credentials are needed here.
Create a separate local .env with ONLY the terminal settings:

```dotenv
POS_API_BASE_URL=http://<MONOBLOCK_1_WIFI_IPV4>:8000
POS_PRINTER_ID=
POS_API_TIMEOUT_SECONDS=10
```

Replace the angle-bracket placeholder with the observed server IP and set the
printer ID to Printer 2's distinct record, never copy Printer 1's ID by default.
Run `.\.venv\Scripts\python.exe pos.py` (or `python pos.py` after activation).
Environment variables override .env; remove stale POS_* environment overrides
if settings unexpectedly point at the wrong server or printer.

From POS2, substitute the actual address:

```powershell
$serverIp = Read-Host 'Monoblock 1 Wi-Fi IPv4'
Test-NetConnection $serverIp -Port 8000
Invoke-RestMethod "http://${serverIp}:8000/health"
```

Expect TcpTestSucceeded=True and status=ok. Health is liveness, not a complete
database/payment check: also login and load catalog. If unreachable, check server
running, bind 0.0.0.0, IP/subnet/SSID, Private profile, firewall rule and AP isolation.
Do not open 5432 as a workaround. Restart POS/reload catalog after reconnecting.

## Shared state, interruptions and printers

Both clients refresh saved orders from the backend. Catalog reload retrieves central
prices, Osh options, addons, presets and workers. Already saved monetary snapshots
do not change. PostgreSQL sequence IDs generate order numbers; payment checks occur
under SELECT FOR UPDATE in the same transaction as the payment/outbox write.

During server/Wi-Fi outage, requests show connection errors and must not be treated
as success. A timeout after sending a write can mean the server committed but the
reply was lost: refresh saved orders before recreating an order. Do not blindly
retry order creation. Saved orders survive backend restarts in PostgreSQL; unsaved
carts are memory-only. No internet-only service is called during core payment.
Telegram messages remain PENDING until processed, or ERROR and retryable on delivery
failure. Run the existing Telegram worker only on the server, never each POS.

Each UI submits its own POS_PRINTER_ID. IDs route server-side PrintJobs, not local
USB access. Actual hardware type must be confirmed on site. Current EscPosPrinter
is an explicit unconfigured adapter: neither USB nor network physical printing is
implemented yet. A failed configured-printer attempt records ERROR; payment stays
PAID. With no printer ID, the UI reports unconfigured and does not submit a PrintJob.

If both printers are NETWORK devices, a future server adapter can reach both. If
each is USB/local, Printer 2 requires a later local printer agent/service or explicit
network transport. Central FastAPI on POS1 cannot access POS2 USB merely from a
printer record. Neither a printer agent nor driver changes are included in 13.1.

## Physical acceptance checklist (pending)

- [ ] Both machines: health, login, catalog, correctly assigned printer IDs.
- [ ] POS1 order visible after POS2 saved-orders refresh; repeat in reverse.
- [ ] Simultaneous creates: distinct numbers, persisted orders, correct totals.
- [ ] Pay different orders concurrently; both PAID.
- [ ] Same pending order paid concurrently: one success, one existing 409 conflict;
      exactly one Payment and one PAID_ORDER event (automated regression also covers this).
- [ ] Admin changes product/Osh/addon prices, presets and worker; both reload correctly.
- [ ] Disconnect ONLY router internet uplink, keep local Wi-Fi active: both logins,
      catalog, create/pay and saved-order sync still work; Telegram stays retryable.
- [ ] Restart FastAPI: client error during outage without crash, then reload/login
      retry; verify previously saved order still exists.
- [ ] Disconnect POS2 Wi-Fi: clear error, no fake success; reconnect and refresh.
- [ ] Confirm actual printer type and record IDs; printing failure leaves PAID.

Development verification: `env -u DEBUG pytest -v` and `alembic check` on PostgreSQL.
Use a dedicated migrated test database: concurrent tests commit scoped fixture rows
and clean them up. Do not run tests against operational restaurant data.

References: [Windows firewall rule parameters](https://learn.microsoft.com/en-us/powershell/module/netsecurity/new-netfirewallrule)
and [Python Windows timezone requirement](https://docs.python.org/3.12/library/zoneinfo.html).
tzdata supplies Asia/Tashkent without requiring an internet lookup at runtime.
