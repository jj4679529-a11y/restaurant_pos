# Windows PowerShell 5.1 updater safety checks. No production PostgreSQL or GitHub
# credentials are used; releases are temporary local folders.
$ErrorActionPreference = 'Stop'
function Assert-Pass([string]$msg) { Write-Host "PASS: $msg" }
function Assert-Fail([string]$msg) { Write-Error "FAIL: $msg"; exit 1 }

foreach ($name in @('install_autostart_windows.ps1', 'update_windows.ps1', 'start-runtime.ps1', 'cleanup_client_transactions.ps1', 'test-deployment.ps1')) {
    $tokens = $null; $parseErrors = $null
    [System.Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot $name), [ref]$tokens, [ref]$parseErrors) | Out-Null
    if ($parseErrors.Count) { Assert-Fail "PowerShell parse failed: $name" }
    Assert-Pass "PowerShell syntax OK: $name"
}

$updater = Get-Content (Join-Path $PSScriptRoot 'update_windows.ps1') -Raw
foreach ($required in @('gh auth status', 'gh run download', 'version.json', 'Wait-ForHealth', 'RestaurantServer.exe', 'RestaurantPOS.exe', 'config/.env')) {
    if ($updater -notmatch [regex]::Escape($required)) { Assert-Fail "Updater control missing: $required" }
}
if ($updater -match 'dropdb|DROP\s+DATABASE|DROP\s+SCHEMA|TRUNCATE|DELETE\s+FROM|alembic\s+downgrade|seed_database') {
    Assert-Fail 'Updater contains a prohibited database operation'
}
Assert-Pass 'Updater static safety controls OK'

$sandbox = Join-Path ([IO.Path]::GetTempPath()) ('pos-update-test-' + [Guid]::NewGuid().ToString('N'))
$install = Join-Path $sandbox 'installed'
$release = Join-Path $sandbox 'release'
$scriptNames = @('update_windows.ps1', 'start-runtime.ps1', 'install_autostart_windows.ps1', 'test-deployment.ps1', 'cleanup_client_transactions.ps1')
foreach ($path in @("$install\app", "$install\config", "$install\media", "$install\logs", "$install\scripts", "$release\app", "$release\scripts")) {
    New-Item -ItemType Directory -Path $path -Force | Out-Null
}
Set-Content -LiteralPath "$install\config\.env" -Value 'preserve-test-sentinel'
Set-Content -LiteralPath "$install\media\sentinel.txt" -Value 'preserve-media'
Set-Content -LiteralPath "$install\logs\sentinel.txt" -Value 'preserve-logs'
@{ version = '1.0.0'; server = $false } | ConvertTo-Json | Set-Content "$install\version.json"
@{ version = '1.0.0'; server = $false } | ConvertTo-Json | Set-Content "$release\version.json"
$hashes = @{}
foreach ($name in @('RestaurantServer.exe', 'RestaurantPOS.exe', 'RestaurantAdmin.exe')) {
    Set-Content -LiteralPath "$install\app\$name" -Value 'old-test-binary'
    Set-Content -LiteralPath "$release\app\$name" -Value 'new-test-binary'
    $hashes[$name] = (Get-FileHash "$release\app\$name" -Algorithm SHA256).Hash
}
$hashes | ConvertTo-Json | Set-Content "$release\app\SHA256.json"
Set-Content "$install\app\SHA256.json" '{}'
foreach ($name in $scriptNames) {
    Set-Content "$install\scripts\$name" 'old-test-script'
    Set-Content "$release\scripts\$name" 'new-test-script'
}
function Get-ScheduledTask { param($TaskName) return $null }

# Same version: no-update path must not touch installed files.
& "$PSScriptRoot\update_windows.ps1" -InstallDirectory $install -ReleaseDirectory $release -NoRestart -Confirm:$false
if ((Get-Content "$install\app\RestaurantPOS.exe") -ne 'old-test-binary') { Assert-Fail 'No-update path modified binaries' }
Assert-Pass 'No-update path preserved installed binary'

# Newer local release: update only replaceable files, preserving .env/media/logs.
@{ version = '1.0.1'; server = $false } | ConvertTo-Json | Set-Content "$release\version.json"
& "$PSScriptRoot\update_windows.ps1" -InstallDirectory $install -ReleaseDirectory $release -NoRestart -Confirm:$false
if ((Get-Content "$install\app\RestaurantPOS.exe") -ne 'new-test-binary') { Assert-Fail 'Update did not replace binary' }
if ((Get-Content "$install\config\.env") -ne 'preserve-test-sentinel') { Assert-Fail '.env modified' }
if ((Get-Content "$install\media\sentinel.txt") -ne 'preserve-media') { Assert-Fail 'Media modified' }
if ((Get-Content "$install\logs\sentinel.txt") -ne 'preserve-logs') { Assert-Fail 'Logs modified' }
if (@(Get-ChildItem "$install\backups" -Recurse -Filter 'files.json').Count -ne 1) { Assert-Fail 'Timestamped backup missing' }
Assert-Pass 'Update preserved config, media, logs and created backup'

# Corrupt release is rejected before replacement; the installed version remains intact.
@{ version = '1.0.2'; server = $false } | ConvertTo-Json | Set-Content "$release\version.json"
Set-Content "$release\app\RestaurantPOS.exe" 'corrupt-binary'
try { & "$PSScriptRoot\update_windows.ps1" -InstallDirectory $install -ReleaseDirectory $release -NoRestart -Confirm:$false; Assert-Fail 'Bad download was accepted' } catch { }
if ((Get-Content "$install\app\RestaurantPOS.exe") -ne 'new-test-binary') { Assert-Fail 'Bad download changed installed binary' }
Assert-Pass 'Bad download rejected without changing installation'

# A failed server start/migration must restore the previous application files.
foreach ($name in @('RestaurantServer.exe', 'RestaurantPOS.exe', 'RestaurantAdmin.exe')) {
    Set-Content "$release\app\$name" 'newer-test-binary'
    $hashes[$name] = (Get-FileHash "$release\app\$name" -Algorithm SHA256).Hash
}
$hashes | ConvertTo-Json | Set-Content "$release\app\SHA256.json"
@{ version = '1.0.3'; server = $true } | ConvertTo-Json | Set-Content "$release\version.json"
try { & "$PSScriptRoot\update_windows.ps1" -InstallDirectory $install -ReleaseDirectory $release -Confirm:$false; Assert-Fail 'Failed server start was accepted' } catch { }
if ((Get-Content "$install\app\RestaurantPOS.exe") -ne 'new-test-binary') { Assert-Fail 'Failed server start did not roll back binary' }
Assert-Pass 'Failed server start restored previous binaries'

Remove-Item -LiteralPath $sandbox -Recurse -Force
Write-Host 'Windows deployment checks PASSED.' -ForegroundColor Green
