[CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'High')]
param(
    [Parameter(Mandatory = $true)][string]$InstallDirectory,
    [string]$DatabaseUrl,
    [string]$BackupDirectory,
    [string]$PgDumpPath,
    [string]$PsqlPath,
    [switch]$DryRun,
    [Parameter(Mandatory = $true)]
    [ValidateScript({
        if ($_ -ne 'DELETE TEST TRANSACTIONS') { throw 'Type exactly: DELETE TEST TRANSACTIONS' }
        $true
    })]
    [string]$ConfirmCleanup
)

# WARNING: MANUAL FINAL-HANDOFF TOOL ONLY. This is destructive and must be used
# only after all acceptance testing is complete. It is never called by autostart,
# updates, deployment tests, or the application. A PostgreSQL backup and the exact
# confirmation phrase are mandatory before it can delete the allowlisted test/demo
# transaction rows. It never deletes catalog, accounts, configuration, media, or schema.
$ErrorActionPreference = 'Stop'
$transactionalTables = @('telegram_outbox', 'print_jobs', 'payments', 'order_item_addons', 'order_items', 'orders')
$protectedTables = @('users', 'categories', 'products', 'price_options', 'add_ons', 'product_addons', 'manual_price_presets', 'delivery_workers', 'printers', 'settings', 'alembic_version')
$root = (Resolve-Path -LiteralPath $InstallDirectory).Path
$appRoot = if (Test-Path -LiteralPath (Join-Path $root 'app\RestaurantServer.exe')) { Join-Path $root 'app' } else { $root }
$isDryRun = $DryRun -or $WhatIfPreference

if (!$DatabaseUrl) {
    $envFile = Join-Path $root 'config\.env'
    if (!(Test-Path -LiteralPath $envFile)) { $envFile = Join-Path $appRoot '.env' }
    if (!(Test-Path -LiteralPath $envFile -PathType Leaf)) { throw 'Database URL was not supplied and no deployment .env was found.' }
    $line = Get-Content -LiteralPath $envFile | Where-Object { $_ -match '^\s*DATABASE_URL\s*=' } | Select-Object -First 1
    if (!$line) { throw 'DATABASE_URL is missing from the deployment .env.' }
    $DatabaseUrl = ($line -replace '^\s*DATABASE_URL\s*=\s*', '').Trim().Trim('"').Trim("'")
}
if ($DatabaseUrl -notmatch '^postgresql(\+[a-z0-9_]+)?://') { throw 'Only a PostgreSQL DATABASE_URL is accepted.' }

function Resolve-PostgresTool([string]$Requested, [string]$Name) {
    if ($Requested) {
        if (!(Test-Path -LiteralPath $Requested -PathType Leaf)) { throw "$Name was not found: $Requested" }
        return (Resolve-Path -LiteralPath $Requested).Path
    }
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if (!$command) { throw "$Name was not found. Install PostgreSQL client tools or supply its path." }
    return $command.Source
}

$psql = Resolve-PostgresTool $PsqlPath 'psql'
function Invoke-ReadOnlyPsql([string]$Sql) {
    $result = $Sql | & $psql --dbname=$DatabaseUrl --set=ON_ERROR_STOP=1 --no-psqlrc --tuples-only --no-align
    if ($LASTEXITCODE -ne 0) { throw 'Read-only database verification failed. No cleanup was attempted.' }
    return $result
}

$countsSql = @'
SELECT 'telegram_outbox' AS table_name, count(*) FROM telegram_outbox
UNION ALL SELECT 'print_jobs', count(*) FROM print_jobs
UNION ALL SELECT 'payments', count(*) FROM payments
UNION ALL SELECT 'order_item_addons', count(*) FROM order_item_addons
UNION ALL SELECT 'order_items', count(*) FROM order_items
UNION ALL SELECT 'orders', count(*) FROM orders
ORDER BY table_name;
'@

Write-Host 'Transactional tables allowed for cleanup:'
$transactionalTables | ForEach-Object { Write-Host " - $_" }
Write-Host 'Protected tables are never targeted:'
$protectedTables | ForEach-Object { Write-Host " - $_" }
Write-Host 'Current row counts (read-only):'
Invoke-ReadOnlyPsql $countsSql | ForEach-Object { Write-Host " $_" }
if ($isDryRun) {
    Write-Host 'DRY RUN: no backup and no database changes were made.'
    return
}

foreach ($process in Get-Process -ErrorAction SilentlyContinue) {
    if ($process.Path -and (Split-Path -Leaf $process.Path) -eq 'RestaurantServer.exe' -and (Split-Path -Parent $process.Path) -eq $appRoot) {
        throw 'Close RestaurantServer.exe before cleanup. No process was stopped.'
    }
}

$pgDump = Resolve-PostgresTool $PgDumpPath 'pg_dump'
if (!$BackupDirectory) { $BackupDirectory = Join-Path $root 'backups' }
if (!(Test-Path -LiteralPath $BackupDirectory)) { New-Item -ItemType Directory -Path $BackupDirectory -Force | Out-Null }
$backupRoot = (Resolve-Path -LiteralPath $BackupDirectory).Path
$backup = Join-Path $backupRoot ('restaurant-pos-before-client-cleanup-' + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss') + '.dump')

if (!$PSCmdlet.ShouldProcess('allowlisted transactional rows', 'Create verified PostgreSQL backup, then remove test/demo transactions')) { return }
& $pgDump --dbname=$DatabaseUrl --format=custom --file=$backup
if ($LASTEXITCODE -ne 0 -or !(Test-Path -LiteralPath $backup -PathType Leaf) -or (Get-Item -LiteralPath $backup).Length -eq 0) {
    throw 'Database backup failed or is empty. No cleanup was attempted.'
}

# ON_ERROR_STOP prevents COMMIT after any error. On failure psql closes its connection
# with the transaction uncommitted, so PostgreSQL rolls it back in full.
$cleanupSql = @'
BEGIN;
DELETE FROM telegram_outbox;
DELETE FROM print_jobs;
DELETE FROM payments;
DELETE FROM order_item_addons;
DELETE FROM order_items;
DELETE FROM orders;

DO $$
DECLARE
    catalog_count integer;
    admin_count integer;
    cashier_count integer;
    worker_count integer;
    settings_count integer;
    order_count integer;
    payment_count integer;
    print_job_count integer;
BEGIN
    SELECT count(*) INTO catalog_count FROM products;
    SELECT count(*) INTO admin_count FROM users WHERE role = 'ADMIN';
    SELECT count(*) INTO cashier_count FROM users WHERE role = 'CASHIER';
    SELECT count(*) INTO worker_count FROM delivery_workers;
    SELECT count(*) INTO settings_count FROM settings;
    SELECT count(*) INTO order_count FROM orders;
    SELECT count(*) INTO payment_count FROM payments;
    SELECT count(*) INTO print_job_count FROM print_jobs;
    IF catalog_count = 0 OR admin_count = 0 OR cashier_count = 0 OR worker_count = 0 OR settings_count = 0 THEN
        RAISE EXCEPTION 'Protected configuration verification failed; transaction rolled back.';
    END IF;
    IF order_count <> 0 OR payment_count <> 0 OR print_job_count <> 0 THEN
        RAISE EXCEPTION 'Transactional cleanup verification failed; transaction rolled back.';
    END IF;
END $$;
COMMIT;
'@

$cleanupSql | & $psql --dbname=$DatabaseUrl --set=ON_ERROR_STOP=1 --no-psqlrc --quiet
if ($LASTEXITCODE -ne 0) { throw "Cleanup failed and was rolled back. The verified backup remains at: $backup" }
Write-Host "Client transactional cleanup complete. Protected catalog/accounts/workers/settings remain; orders/payments/print jobs are empty. Backup: $backup"
