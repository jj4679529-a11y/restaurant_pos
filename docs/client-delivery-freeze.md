# Final delivery: safe operation and remaining acceptance

## Required sequence

1. Stop trading and close POS/Admin/Server normally. Back up PostgreSQL with the
   operator's established backup procedure; retain the existing `.env` and `media`.
2. Build on Windows from this revision (`pip install -r requirements.txt`,
   `pip install pyinstaller`, then `python -m PyInstaller --noconfirm --clean`
   with `server.spec`, `pos.spec`, and `admin.spec`, separately). GitHub Actions
   does the same and creates `SHA256.json` for the three executables.
3. Copy only binaries via `scripts/update_windows.ps1`. On the server:

```powershell
.\update_windows.ps1 -InstallDirectory C:\RestaurantPOS -ReleaseDirectory C:\POSRelease -Server -WhatIf
.\update_windows.ps1 -InstallDirectory C:\RestaurantPOS -ReleaseDirectory C:\POSRelease -Server
```

Use actual detected folders, not those example paths. On POS2 omit `-Server`.
The updater validates SHA256, refuses running binaries, creates recoverable binary
backups, replaces only three allowlisted executables, and on POS1 runs
`RestaurantServer.exe --migrate`. It does not delete any database/config/media.
SHA256 validates integrity, not publisher identity: obtain the release from the
trusted project Actions run. Do not downgrade the database on update failure.

4. `RestaurantServer.exe --migrate` supports source-free Windows installation and
   applies only forward Alembic changes. It does not seed or reset data.
5. In Admin → Menyu, use **Yakuniy menyuni tayyorlash** once, review the result,
   and set all real prices. Missing records have zero/unconfigured prices, never
   invented selling prices. Existing prices are preserved. Old two-egg links are
   made inactive, not deleted; Bedana tuxum gets a distinct record with its own price.
6. Kompot/Ayran from legacy liter configuration are blocked from checkout until
   Admin explicitly saves their **dona price**. No conversion from liter price to
   piece price is inferred. Their existing prices are not silently overwritten.
7. Configure Osh/soups and bread via **Porsiya / non variantlari**; arbitrary
   positive portion quantities and prices are supported. Do not run legacy full
   seed on production. Review legacy placeholders/categories and deactivate unused
   products through Admin; historical rows are never deleted.

## Windows startup

Run the startup installer in an elevated PowerShell if configuring the PostgreSQL
service or firewall. Detect the exact service with `Get-CimInstance Win32_Service`;
do not assume its name. Example (replace paths/service with verified values):

```powershell
.\install_autostart_windows.ps1 -InstallDirectory C:\RestaurantPOS -Server -PostgresServiceName postgresql-x64-16 -WhatIf
.\install_autostart_windows.ps1 -InstallDirectory C:\RestaurantPOS -Server -PostgresServiceName postgresql-x64-16
```

On POS2 omit `-Server` and `-PostgresServiceName`. The per-user tasks start on login,
not before login; they retry failure three times, one minute apart. They use no
stored passwords. Set `AUTO_START_WITH_WINDOWS=false` and launch POS once to remove
the older Run-key registration when using these tasks. The only added firewall
rule allows TCP 8000 from LocalSubnet on Private networks. No 5432 rule is created;
review existing firewall rules separately. PostgreSQL remains its normal service.
The installer also creates per-user Desktop and Start Menu shortcuts for
`RestaurantPOS.exe` and `RestaurantAdmin.exe`; it does not auto-open Admin.

## Acceptance / non-claims

- Verify Admin cashier creation (name/phone/login/password), login and deactivation.
- Set real prices for every final-menu product; verify cashier refresh and images.
- Verify all Osh portions/addons, Go‘sht custom amount ≥5000, soup portions, bread
  Butun/Yarim/Chorak, Manti counts, Jizz manual amount, salads, Choy/Novot, Kompot/Ayron
  piece prices, and cold-drink volume metadata without volume-based charging.
- Verify saved CHAYKHANA and DELIVERY orders, active-worker requirement, one payment,
  independent print failure, and payer/worker/product/category report totals.
- Business-day settings default to 06:00 / Asia/Tashkent. Changes affect subsequent
  order-day assignment; existing order.business_day_id and amounts remain unchanged.
  Product/category report amounts include addons in each parent item's snapshot;
  category labels/grouping use the current catalog category (historical category
  snapshots are not stored by the existing schema).
- Check 1366×768 at 100% and 125% Windows scaling on the physical touchscreen.
- Verify login autostart, failure restart, binary update, and restart persistence.
- Confirm Telegram enabled/configured; disconnect internet while retaining LAN,
  take payments, restore internet and verify queued delivery. No real Telegram
  calls are made by tests.
- The existing ESC/POS adapter is still unconfigured: physical printing is **not
  certified** by mocked tests. Hardware acceptance and Windows builds must succeed
  before CLIENT READY can be YES.

## Final transactional test-data cleanup

Only after the client has accepted all testing, stop `RestaurantServer.exe` and
run this on Monoblock 1. It requires the exact quoted confirmation phrase
`DELETE TEST TRANSACTIONS`, takes a PostgreSQL custom-format backup first, then deletes only transactional rows:
orders, order items/addons, payments, print jobs, Telegram outbox rows and
test-only output rows. It preserves business-day configuration, schema, menu/catalog, presets, images,
users, workers, printers and settings. It verifies that catalog/users/settings
remain and that orders/payments are empty before reporting success.

```powershell
.\cleanup_client_transactions.ps1 -InstallDirectory C:\RestaurantPOS -ConfirmCleanup 'DELETE TEST TRANSACTIONS' -WhatIf
.\cleanup_client_transactions.ps1 -InstallDirectory C:\RestaurantPOS -ConfirmCleanup 'DELETE TEST TRANSACTIONS' -Confirm
```

The backup is written to `C:\RestaurantPOS\backups` by default. Keep it until
handoff is accepted; restore it with the restaurant's established PostgreSQL
restore procedure if cleanup was invoked too early.
