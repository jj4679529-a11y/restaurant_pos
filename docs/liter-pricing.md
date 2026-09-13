# Light receipt and liter-based drinks

LITER drinks reuse the existing Product.base_price as the price per liter. The
cashier selects a Decimal volume; the existing UI and backend calculation multiply
quantity by the unit-price snapshot. No database, order, payment or printer rules
were changed, and no migration was added.

Admin: choose Sotish turi = Litr, then enter **1 litr narxi**. Cashier reloads the
catalog to receive the price. Product cards show `so‘m / litr`.

Click a liter product to open the volume selector: 0.5, 1, 1.5 and 2 L are quick
choices, not allowed-value restrictions. BOSHQA HAJM opens a decimal keypad with
keyboard entry, clear and backspace. Both `1.5` and `1,5` are accepted. Positive
volumes use at most three fractional places, matching the existing API/DB precision.
Zero, negatives, malformed text and non-whole-UZS resulting totals are rejected;
amounts are not silently rounded. Integer-money input remains separate.

Cart rows show the product subtotal once, secondary addon amounts and clean
quantities. Liter rows show the volume and per-liter price; Tahrirlash reopens
the volume selector instead of ambiguous +/- liter changes. The overall total
still includes all addons. Internal request quantities retain three decimals;
display formatting does not change snapshots or calculations.

Receipt list/viewport palettes and card styles explicitly use light surfaces even
under a dark system palette. Main line, addon text, local controls and selection
are styled through the shared theme.

Verification: `tests/test_liter_cart.py` covers decimal entry, volume totals,
integer-money validation, receipt formatting/dark palette, Admin price changes,
cashier reload and a real API order with the same calculated total. Full suite
was run against a disposable PostgreSQL database because the local restaurant
database has owner-edited seed prices; those prices were not overwritten.
