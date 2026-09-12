# Phase 12 — Admin panel

Run the backend with the existing database and environment, then launch the
separate Admin application:

```bash
source .venv/bin/activate
pip install -r requirements.txt
env -u DEBUG uvicorn main:app --host 127.0.0.1 --port 8000
# Another terminal, same virtualenv:
python admin.py
```

Use an existing ADMIN login. CASHIER is rejected before the dashboard, and every
Admin write is independently role-checked by FastAPI. JWT is runtime-only.
The Admin app uses `POS_API_BASE_URL`/`POS_API_TIMEOUT_SECONDS` and never imports
the database module. Do not distribute the backend `.env` to remote terminals.

## Pages

- Dashboard: active category/product/worker/user/cashier/printer counts.
- Categories: create, rename, sort, deactivate/reactivate.
- Products: category filter, category/unit/base price/manual flag, image, active.
- Addons: name, fixed piece price or manual flag, active.
- Presets: product/addon target, integer amount, sort order, active; inactive
  records remain visible so they can be reactivated.
- Workers: name, phone, active.
- Users: name, username, role, active and new password only. Blank replacement
  password means unchanged. Existing self-deactivation protection is retained.
- Printers: name, terminal, USB/NETWORK, address, active. The displayed printer
  record ID is the value for that terminal's `POS_PRINTER_ID`. WINDOWS is not
  offered because the verified database enum supports USB/NETWORK only.
- Settings: only restaurant_name, business_day_start and timezone. The latter
  two are constrained to 06:00 / Asia/Tashkent; changing backend day-boundary
  semantics is not part of Admin UI. Environment secrets never appear here.

Select a roomy list row and press TAHRIRLASH (or double-click it). Save/cancel
is explicit; leaving a changed form asks for confirmation. Deactivation asks
for confirmation. Normal UI does not hard-delete records.

## Restaurant pricing

Select Osh on Products, then `OSH: 0.5 / 1 NARXLARI`. Enter the two actual
restaurant prices. One transaction locks the product/options, updates exactly
two active canonical options and deactivates legacy variants without deleting
historical IDs. No example amounts are automatically populated.

Osh's ordinary editor locks base/manual/unit/name controls. Jizz and Go'sht
lock their manual-price capability on; Go'sht cannot be created as a Product
through this editor. Tuxum/Qazi are fixed-price per-piece addons. Save an existing
unconfigured Jizz product once to enable its manual mode before adding presets.

Products -> `QO‘SHIMCHA BOG‘LASH / AJRATISH` selects an addon and changes the
relationship's active/required flags; unlink is a soft deactivation.

Reopen the cashier application (or reload its catalog) to see Admin changes.
Existing saved orders retain their monetary snapshots.

## Image storage

Choose/replace uploads the image over authenticated HTTP, stages a new asset and
updates the draft reference. Save applies the reference to the Product. Remove
clears the reference on Save; it does not delete a potentially shared image file.
Cancelling an image edit can leave an unreferenced staged asset, intentionally
retained for safe future maintenance rather than destructive automatic cleanup.

Backend accepts PNG/JPEG/WebP up to 5 MB and 12 megapixels, decodes and re-encodes
to a randomly named JPEG under PRODUCT_MEDIA_DIR (default media/products).
No original filename, absolute client path, metadata or binary is stored in DB.
Pillow is pinned in requirements; see its [image validation documentation](https://pillow.readthedocs.io/en/stable/reference/Image.html).

## Minimal API additions (Admin only)

- GET/POST `/api/admin/printers`; PUT `/api/admin/printers/{id}`.
- GET `/api/admin/manual-price-presets` includes inactive presets.
- GET `/api/admin/products/{id}/addons`; PUT matching `/{addon_id}` for link state.
- PUT `/api/admin/products/{id}/osh-prices` accepts half_price/full_price atomically.
- GET `/api/admin/settings`; PATCH `/{key}` with an explicit safe allowlist.
- POST `/api/admin/product-images` accepts a bounded raw image body.

Other CRUD uses the existing catalog/users/presets/worker APIs. No model or
migration change is required. Printer drivers, analytics, inventory and
two-monoblock deployment remain out of scope. HTTP calls are synchronous with
timeouts; slow servers may temporarily pause the desktop UI.

## Checks

```bash
env -u DEBUG pytest -v tests/test_admin_ui.py
env -u DEBUG pytest -v
env -u DEBUG alembic check
```

Tests use rollback-isolated PostgreSQL fixtures and actual Qt forms/API handlers.
They do not configure real restaurant prices. Native GUI acceptance must also
be performed with the restaurant's own configuration before operational use.
