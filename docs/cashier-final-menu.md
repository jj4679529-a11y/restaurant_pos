# Cashier menu / Phase 11.1

## Migration

`b4a91c6f207e` follows `733f8f399dc3`. It adds only nullable
`products.image_path` and `manual_price_presets`. No order/payment/transaction
schema is changed. Presets have exactly one product/addon foreign key, positive
integer UZS amount, ordering, active flag and unique target/amount constraints.

```bash
source .venv/bin/activate
env -u DEBUG alembic heads
env -u DEBUG alembic current
env -u DEBUG alembic upgrade head
env -u DEBUG alembic check
```

## Initial menu configuration

Provide the restaurant's real values through environment variables or the
gitignored backend `.env`; do not put credentials into this document or source.

- `OSH_HALF_PRICE`, `OSH_FULL_PRICE`: required on first final-menu seed.
- `EGG_ONE_PRICE`, `EGG_TWO_PRICE`, `QAZI_PRICE`: initial whole-UZS fixed prices.
- `GOSHT_MANUAL_PRESETS`, `JIZZ_MANUAL_PRESETS`: JSON arrays of positive whole-UZS
  amounts chosen by the restaurant; default empty, not invented example prices.
- Existing `ADMIN_USERNAME`, `ADMIN_PASSWORD` remain the seed's bootstrap config.

```bash
env -u DEBUG python -m app.seed.seed_database
env -u DEBUG python -m app.seed.seed_database
```

Seed creates exactly two **active** Osh options: `0.5 porsiya` and `1 porsiya`.
Legacy option rows are deactivated, not deleted: historical orders retain their
foreign keys and monetary snapshots. Existing canonical portion prices and
preset edits survive subsequent seeds. Fixed addon prices initialize only when
currently zero. Go'sht remains a manual AddOn; Jizz is a manual Product and its
old options are deactivated. Missing portion prices abort/roll back the seed.

The selected option's price is the exact charge for that portion. Order item
`quantity=1` means one selected portion, even when the option describes `0.5`.
Two half-portions use quantity 2. Do not halve the configured price again.
Addon quantities are totals for the cart line, not automatically multiplied by
Osh count. Change egg/Qazi counts in the product dialog explicitly.

## Catalog API

Existing authenticated product GET responses add `image_path` and
`manual_price_presets`; linked addons include active presets too.
Existing Admin product PATCH supports `image_path`.

- GET `/api/manual-price-presets`: Cashier/Admin, active presets, optional
  `product_id`/`addon_id`, `limit`/`offset`.
- POST `/api/manual-price-presets`: Admin, exactly one target, amount,
  optional `sort_order`/`is_active`. Target must allow manual prices.
- PATCH `/api/manual-price-presets/{id}`: Admin edits amount/order/active flag.
- GET `/api/product-images/{reference}`: authenticated local media delivery.

Use existing Admin PriceOption PATCH for subsequent portion price changes;
keep the two canonical portion identities. No Admin GUI is included yet.

## Offline media

Copy PNG/JPEG/WebP files into backend `media/products/` or configure an absolute
`PRODUCT_MEDIA_DIR` on the server. Store only relative forward-slash references
such as `menu/osh.png` in Product.image_path. The cashier fetches them over the
same LAN HTTP API; no internet image host or direct PostgreSQL access is used.
Traversal and symlinks escaping the media directory are refused. No upload
endpoint is provided yet. Missing/unreadable images use a drawn placeholder.
Copy this media directory alongside the backend on later Windows deployment;
do not copy a server's absolute paths into product records.

## Terminal / launch

Terminal configuration contains only `POS_API_BASE_URL`, `POS_PRINTER_ID` and
optional `POS_API_TIMEOUT_SECONDS`. No database URL or JWT signing key belongs
on a separate cashier terminal. Access tokens stay in runtime memory.

```bash
# Terminal 1
source .venv/bin/activate
env -u DEBUG uvicorn main:app --host 127.0.0.1 --port 8000

# Terminal 2
source .venv/bin/activate
python pos.py
```

Before Save, cart editing is local only. Save creates PENDING and locks the
cart. Checkout pays then prints. Print errors preserve PAID, exposing retry
print and new-order actions. Retry print never pays again. A lost PAY response
is reconciled with order GET before another payment attempt. A missing printer
does not block payment. Actual printing still requires a configured operational
backend printer adapter/device.

Cashier navigation now includes `YANGI BUYURTMA` and `SAQLANGAN BUYURTMALAR`.
History opens separately without modifying the draft cart, with status filters
and paginated newest-first rows. Details are read-only and display monetary
snapshots and the selected PriceOption ID (the order API does not expose a
historical variant name). PENDING may pay then print; PAID prints only;
CANCELLED has neither action. Returning to a new order after saving leaves the
saved order in history. Pressing new order with an unsaved draft preserves it.

Osh's dialog never allows manual base prices, even if the incoming catalog flag
is incorrect. It requires the two configured canonical portion choices; missing
or ambiguous configuration produces an explicit unavailable state, not a keypad.
Manual addon presets appear directly in the product dialog; empty collections
show `Tezkor narxlar sozlanmagan` while custom keypad entry remains available.

## Verification

```bash
env -u DEBUG pytest -v tests/test_ui_final_menu.py tests/test_ui_state.py tests/test_ui_api_client.py
env -u DEBUG pytest -v
```

Offscreen Qt tests cover widget behavior but are not manual GUI acceptance.
Before declaring complete, verify live login, categories/images, both Osh
portions, egg/Qazi counts, manual/preset Go'sht/Jizz, edit/remove, delivery worker,
save, pay, physical print, failed-print PAID state and print-only retry.

HTTP requests currently run synchronously with bounded timeouts; a slow backend
can temporarily pause the touchscreen. This remains a deployment UX limitation.
