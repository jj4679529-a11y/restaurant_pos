# Cashier + Admin UX refinement

This is a presentation change; database, authentication, payment, cancellation,
Telegram, business-day and terminal configuration rules remain unchanged.

Cashier: compact top navigation, selected categories, four product columns at
1366x768, independent menu scrolling, line-local quantity/edit/remove controls,
empty-cart explanation and checkout inside the receipt column. DRAFT shows Save;
PENDING shows Pay + Print; PAID offers reprint/new order; CANCELLED is read-only.
Existing automatic reset after successful payment+printing is preserved.

Admin: 236px navigation, summary cards, compact menu rows with images, owner-facing
unit names and hidden image references. Menyu and Menyu guruhlari remain separate
screens within the same menu concept. Select Osh settings directly from navigation;
editing Osh from the menu also routes there instead of the generic price editor.
Only 0.5 and 1 portion prices are editable, saved atomically through the existing API.
Addon prices and manual quick-price changes are separate saves, explicitly labeled;
the entire screen is not presented as one atomic transaction.

On Osh settings, use the addon price action for Tuxum/Qazi and Tezkor narxlar for
Go'sht. For Jizz, select it under Menyu then TEZKOR NARXLARNI SOZLASH. Numeric dialogs
add/edit quick amounts; existing records can be deactivated, not deleted. Cashier
reloads the catalog to receive these changes without restarting. Jizz/Go'sht quick
choices precede the custom numeric keypad; Osh never uses a manual-price fallback.

Product images use the existing upload/preview/removal API and safe relative paths.
The reference field is retained internally, not displayed to the owner. No migration.

Verification includes real Qt geometry at 1280x720, 1366x768 and 1920x1080,
PostgreSQL-backed Admin-to-cashier price/preset tests, existing image safety tests,
and all prior checkout/reprint/payment invariants. Native macOS Qt tests also run;
this does not replace acceptance by the owner on an actual Windows touchscreen.

Known limitations: catalog/admin HTTP requests remain synchronous with the existing
timeout, so slow networks may temporarily pause the window despite the loading/error
message. No networking redesign is included. Existing saved-order dialogs retain
their touch-friendly rows and status actions. An addon save refreshes its summary
without overwriting unsaved Osh portion inputs.

No floating window named Keyboard is created by app/ui or either launcher. The
previous screenshot's overlay cannot be conclusively attributed from current process
inspection. If it is macOS Accessibility Keyboard, manage it in macOS Accessibility
settings, not POS business/UI code. Windows touch keyboard configuration is separate.
