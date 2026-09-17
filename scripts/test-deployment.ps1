# Windows PowerShell 5.1 deployment smoke checks. No PostgreSQL, real tasks or services changed.
$ErrorActionPreference = 'Stop'
function Assert-Pass([string]$msg) { Write-Host "PASS: $msg" }
function Assert-Fail([string]$msg) { Write-Error "FAIL: $msg"; exit 1 }

foreach ($name in @('install_autostart_windows.ps1', 'update_windows.ps1', 'start-runtime.ps1', 'cleanup_client_transactions.ps1', 'test-deployment.ps1')) {
    $tokens = $null; $parseErrors = $null
    [System.Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot $name), [ref]$tokens, [ref]$parseErrors) | Out-Null
    if ($parseErrors.Count) { Assert-Fail "PowerShell parse failed: $name" }
    Assert-Pass "PowerShell syntax OK: $name"
}

$distExeDir = Join-Path $PSScriptRoot '..\dist'
if ((Test-Path $distExeDir) -and (Get-ChildItem $distExeDir -Filter '*.exe' -ErrorAction SilentlyContinue).Count -gt 0) {
    foreach ($name in @('RestaurantServer.exe', 'RestaurantPOS.exe', 'RestaurantAdmin.exe')) {
        if (!(Test-Path (Join-Path $distExeDir $name) -PathType Leaf)) { Assert-Fail "Missing executable: $name" }
        Assert-Pass "Executable exists: $name"
    }
} else {
    Write-Host "SKIP: Executable check (no dist/ folder with .exe files)"
}

$sandbox = Join-Path ([IO.Path]::GetTempPath()) ('pos-update-test-' + [Guid]::NewGuid().ToString('N'))
$install = Join-Path $sandbox 'installed'
$release = Join-Path $sandbox 'release'
foreach ($path in @("$install\app", "$install\config", "$install\media", "$release\app")) {
    New-Item -ItemType Directory -Path $path -Force | Out-Null
}
Set-Content -LiteralPath "$install\config\.env" -Value 'preserve-test-sentinel'
Set-Content -LiteralPath "$install\media\sentinel.txt" -Value 'preserve-media'
$hashes = @{}
foreach ($name in @('RestaurantServer.exe', 'RestaurantPOS.exe', 'RestaurantAdmin.exe')) {
    Set-Content -LiteralPath "$install\app\$name" -Value 'old-test-binary'
    Set-Content -LiteralPath "$release\app\$name" -Value 'new-test-binary'
    $hashes[$name] = (Get-FileHash "$release\app\$name" -Algorithm SHA256).Hash
}
$hashes | ConvertTo-Json | Set-Content "$release\app\SHA256.json"
function Get-ScheduledTask { param($TaskName) return $null }

if (!(Test-Path "$install\config\.env")) { Assert-Fail "Config .env missing" }
Assert-Pass "Config .env exists"

& "$PSScriptRoot\update_windows.ps1" -InstallDirectory $install -ReleaseDirectory $release -WhatIf
if ((Get-Content "$install\app\RestaurantPOS.exe") -ne 'old-test-binary') { Assert-Fail "WhatIf modified binaries" }
Assert-Pass "WhatIf does not modify binaries"

& "$PSScriptRoot\update_windows.ps1" -InstallDirectory $install -ReleaseDirectory $release
foreach ($name in $hashes.Keys) {
    if ((Get-FileHash "$install\app\$name").Hash -ne $hashes[$name]) { Assert-Fail "Binary replacement failed: $name" }
    Assert-Pass "Binary replaced OK: $name"
}

if ((Get-Content "$install\config\.env") -ne 'preserve-test-sentinel') { Assert-Fail "Configuration modified" }
Assert-Pass "Config .env preserved"
if ((Get-Content "$install\media\sentinel.txt") -ne 'preserve-media') { Assert-Fail "Media modified" }
Assert-Pass "Media preserved"

if (@(Get-ChildItem "$install\app\binary-backups" -Recurse -Filter '*.exe').Count -ne 3) { Assert-Fail "Backup missing" }
Assert-Pass "Binary backup exists (3 files)"

foreach ($name in @('install_autostart_windows.ps1', 'update_windows.ps1', 'start-runtime.ps1')) {
    $content = Get-Content (Join-Path $PSScriptRoot $name) -Raw
    if ($content -match 'dropdb|DROP\s+DATABASE|DROP\s+SCHEMA|DELETE\s+FROM\s+(users|orders|settings)|TRUNCATE\s+(users|orders|settings)') {
        Assert-Fail "Destructive DB command found in $name"
    }
    Assert-Pass "No destructive DB commands in $name"
}

# Cleanup is intentionally destructive, but manual-only and constrained to a fixed
# transactional allowlist. This test never invokes it or connects to PostgreSQL.
$cleanup = Get-Content (Join-Path $PSScriptRoot 'cleanup_client_transactions.ps1') -Raw
if ($cleanup -notmatch "DELETE TEST TRANSACTIONS" -or $cleanup -notmatch 'pg_dump' -or $cleanup -notmatch 'BEGIN;' -or $cleanup -notmatch 'COMMIT;') {
    Assert-Fail 'Cleanup safety controls are missing'
}
if ($cleanup -match 'DELETE\s+FROM\s+(users|categories|products|price_options|add_ons|product_addons|manual_price_presets|delivery_workers|printers|settings|business_days|alembic_version)') {
    Assert-Fail 'Cleanup targets a protected table'
}
Assert-Pass 'Cleanup is manual-only, backup-gated, transactional, and allowlisted'

$realInstall = $args[0]
if ($realInstall) {
    $serverExe = Join-Path $realInstall 'app\RestaurantServer.exe'
    if (!(Test-Path $serverExe)) { Assert-Fail "Server executable not found at $serverExe" }
    Assert-Pass "Server executable found at install path"
    try {
        $health = Invoke-RestMethod -Uri 'http://localhost:8000/health' -TimeoutSec 3
        if ($health.status -eq 'ok') { Assert-Pass "Health endpoint OK" }
        else { Assert-Fail "Health endpoint unexpected response" }
    } catch {
        Write-Host "SKIP: Health endpoint not reachable (server not running)"
    }
    try {
        $port = Test-NetConnection -ComputerName localhost -Port 8000 -WarningAction SilentlyContinue
        if ($port.TcpTestSucceeded) { Assert-Pass "Port 8000 is reachable" }
        else { Write-Host "SKIP: Port 8000 not reachable (server not running)" }
    } catch {
        Write-Host "SKIP: Port 8000 test unavailable"
    }
} else {
    Write-Host "SKIP: Health/port checks require a running server (pass install path as argument)"
}

Write-Host ''
Write-Host '========================================' -ForegroundColor Green
Write-Host 'Windows 5.1 deployment checks PASSED.' -ForegroundColor Green
Write-Host '========================================' -ForegroundColor Green
