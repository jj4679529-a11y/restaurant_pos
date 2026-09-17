[CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'High')]
param(
    [string]$InstallDirectory,
    [string]$ReleaseDirectory,
    [switch]$Server,
    [switch]$NoRestart,
    [string]$Repository,
    [int]$HealthTimeoutSeconds = 60
)

# Manual updater only. It replaces a fixed application/script allowlist and version.json.
# It never copies or deletes config/.env, media, logs, PostgreSQL files, or restaurant data.
# GitHub credentials are obtained only from an existing `gh auth login` session.
$ErrorActionPreference = 'Stop'
$script:AppNames = @('RestaurantServer.exe', 'RestaurantPOS.exe', 'RestaurantAdmin.exe', 'SHA256.json')
$script:ScriptNames = @('update_windows.ps1', 'start-runtime.ps1', 'install_autostart_windows.ps1', 'test-deployment.ps1', 'cleanup_client_transactions.ps1')

function Write-Step([string]$Number, [string]$Message) { Write-Host "[$Number/7] $Message" }
function Read-Version([string]$Path) {
    if (!(Test-Path -LiteralPath $Path -PathType Leaf)) { throw "version.json topilmadi: $Path" }
    $data = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    if (!$data.version -or $data.version -notmatch '^\d+\.\d+\.\d+([-.][0-9A-Za-z.-]+)?$') { throw 'version.json has an invalid semantic version.' }
    return $data
}
function Get-VersionObject([string]$Value) {
    $core = ($Value -split '[-+]')[0]
    return [Version]$core
}
function Resolve-ReleaseRoot([string]$Path) {
    $candidate = Get-ChildItem -LiteralPath $Path -Filter version.json -File -Recurse | Select-Object -First 1
    if (!$candidate) { throw 'Yuklangan paketda version.json topilmadi.' }
    $root = $candidate.Directory.FullName
    if (!(Test-Path -LiteralPath (Join-Path $root 'app\RestaurantPOS.exe')) -or !(Test-Path -LiteralPath (Join-Path $root 'scripts\update_windows.ps1'))) {
        throw 'Yuklangan paketning app/ yoki scripts/ tuzilmasi noto‘g‘ri.'
    }
    return $root
}
function Test-Release([string]$Root) {
    foreach ($name in $script:AppNames) {
        if (!(Test-Path -LiteralPath (Join-Path $Root "app\$name") -PathType Leaf)) { throw "Paketda app\\$name topilmadi." }
    }
    foreach ($name in $script:ScriptNames) {
        if (!(Test-Path -LiteralPath (Join-Path $Root "scripts\$name") -PathType Leaf)) { throw "Paketda scripts\\$name topilmadi." }
    }
    $hashes = Get-Content -LiteralPath (Join-Path $Root 'app\SHA256.json') -Raw | ConvertFrom-Json
    foreach ($name in @('RestaurantServer.exe', 'RestaurantPOS.exe', 'RestaurantAdmin.exe')) {
        $file = Join-Path $Root "app\$name"
        if (!$hashes.$name -or (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash -ne $hashes.$name) { throw "SHA256 tekshiruvi muvaffaqiyatsiz: $name" }
    }
}
function Stop-InstalledProcess([string]$Name, [string]$AppRoot) {
    $matches = @(Get-Process -Name ([IO.Path]::GetFileNameWithoutExtension($Name)) -ErrorAction SilentlyContinue | Where-Object {
        $_.Path -and (Split-Path -Parent $_.Path) -eq $AppRoot
    })
    foreach ($process in $matches) {
        Stop-Process -Id $process.Id -ErrorAction Stop
        $process.WaitForExit(15000)
        if (!$process.HasExited) { throw "$Name xavfsiz to‘xtamadi." }
    }
}
function Wait-ForHealth([int]$TimeoutSeconds) {
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        try {
            $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 3
            if ($health.status -eq 'ok') { return $true }
        } catch { }
        Start-Sleep -Seconds 2
    }
    return $false
}
function Copy-ReleaseFile([string]$Source, [string]$Destination) {
    $parent = Split-Path -Parent $Destination
    if (!(Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    Copy-Item -LiteralPath $Source -Destination $Destination -Force
}

if (!$InstallDirectory) { $InstallDirectory = Split-Path -Parent $PSScriptRoot }
$installation = (Resolve-Path -LiteralPath $InstallDirectory).Path
$appRoot = Join-Path $installation 'app'
$scriptsRoot = Join-Path $installation 'scripts'
if (!(Test-Path -LiteralPath $appRoot -PathType Container)) { throw 'C:\\RestaurantPOS\\app topilmadi. -InstallDirectory ni tekshiring.' }
$installedVersion = Read-Version (Join-Path $installation 'version.json')
$isServer = $Server -or ($installedVersion.server -ne $false)

Write-Step '1' 'Yangilanish tekshirilmoqda...'
if ($ReleaseDirectory) {
    $releaseRoot = Resolve-ReleaseRoot ((Resolve-Path -LiteralPath $ReleaseDirectory).Path)
} else {
    if (!(Get-Command gh -ErrorAction SilentlyContinue)) { throw 'GitHub CLI (gh) topilmadi. Bir marta gh auth login qiling va qayta urinib ko‘ring.' }
    & gh auth status --hostname github.com *> $null
    if ($LASTEXITCODE -ne 0) { throw 'GitHub autentifikatsiyasi yo‘q. gh auth login qiling va qayta urinib ko‘ring.' }
    $repo = if ($Repository) { $Repository } elseif ($installedVersion.repository) { [string]$installedVersion.repository } else { throw 'Repository version.json da ko‘rsatilmagan.' }
    $branch = if ($installedVersion.branch) { [string]$installedVersion.branch } else { 'phase-13-two-monoblock' }
    $workflow = if ($installedVersion.workflow) { [string]$installedVersion.workflow } else { 'build-windows.yml' }
    $run = (& gh run list --repo $repo --workflow $workflow --branch $branch --status success --limit 1 --json databaseId | ConvertFrom-Json | Select-Object -First 1)
    if (!$run -or !$run.databaseId) { throw 'Muvaffaqiyatli Windows build topilmadi. GitHub Actions va gh auth login holatini tekshiring.' }
    $downloadRoot = Join-Path ([IO.Path]::GetTempPath()) ('restaurant-pos-update-' + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $downloadRoot -Force | Out-Null
    try {
        Write-Step '3' 'Yuklanmoqda...'
        & gh run download $run.databaseId --repo $repo --name restaurant-pos-deployment --dir $downloadRoot
        if ($LASTEXITCODE -ne 0) { throw 'GitHub paketini yuklab bo‘lmadi.' }
        $releaseRoot = Resolve-ReleaseRoot $downloadRoot
    } catch {
        if (Test-Path -LiteralPath $downloadRoot) { Remove-Item -LiteralPath $downloadRoot -Recurse -Force }
        throw
    }
}

Test-Release $releaseRoot
$releaseVersion = Read-Version (Join-Path $releaseRoot 'version.json')
if ((Get-VersionObject $releaseVersion.version) -le (Get-VersionObject $installedVersion.version)) {
    Write-Host 'Restaurant POS eng so‘nggi versiyada.'
    Write-Host 'Restaurant POS is already up to date'
    return
}
Write-Step '2' ("Yangi versiya topildi: " + $releaseVersion.version)
if ($ReleaseDirectory) { Write-Step '3' 'Paket tekshirildi.' }

$backup = Join-Path $installation ('backups\update-' + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N'))
$backupFiles = @()
Write-Step '4' 'Backup olinmoqda...'
if (!$PSCmdlet.ShouldProcess($installation, 'Back up and replace only app/, scripts/, and version.json')) { return }
New-Item -ItemType Directory -Path $backup -Force | Out-Null
foreach ($relative in (@($script:AppNames | ForEach-Object { "app\\$_" }) + @($script:ScriptNames | ForEach-Object { "scripts\\$_" }) + @('version.json'))) {
    $current = Join-Path $installation $relative
    $backupPath = Join-Path $backup $relative
    $backupFiles += [PSCustomObject]@{ Relative = $relative; Existed = (Test-Path -LiteralPath $current -PathType Leaf) }
    if (Test-Path -LiteralPath $current -PathType Leaf) { Copy-ReleaseFile $current $backupPath }
}
$backupFiles | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $backup 'files.json') -Encoding UTF8

$tasks = @()
try {
    foreach ($taskName in @('RestaurantPOS-Server', 'RestaurantPOS-Cashier')) {
        $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        if ($task -and $task.State -ne 'Disabled') { Disable-ScheduledTask -TaskName $taskName | Out-Null; $tasks += $taskName }
    }
    Stop-InstalledProcess 'RestaurantPOS.exe' $appRoot
    Stop-InstalledProcess 'RestaurantServer.exe' $appRoot
    $adminOpen = @(Get-Process -Name 'RestaurantAdmin' -ErrorAction SilentlyContinue | Where-Object { $_.Path -and (Split-Path -Parent $_.Path) -eq $appRoot })
    if ($adminOpen.Count) { throw 'RestaurantAdmin.exe ochiq. Uni yoping va qayta urinib ko‘ring.' }

    Write-Step '5' 'Dastur yangilanmoqda...'
    foreach ($name in $script:AppNames) { Copy-ReleaseFile (Join-Path $releaseRoot "app\\$name") (Join-Path $appRoot $name) }
    foreach ($name in $script:ScriptNames) { Copy-ReleaseFile (Join-Path $releaseRoot "scripts\\$name") (Join-Path $scriptsRoot $name) }
    Copy-ReleaseFile (Join-Path $releaseRoot 'version.json') (Join-Path $installation 'version.json')

    if ($isServer -and !$NoRestart) {
        & (Join-Path $appRoot 'RestaurantServer.exe') --migrate
        if ($LASTEXITCODE -ne 0) { throw 'Forward migration muvaffaqiyatsiz. Dastur fayllari qaytariladi; PostgreSQL o‘zgartirilmaydi.' }
        Start-Process -FilePath (Join-Path $appRoot 'RestaurantServer.exe') -WorkingDirectory $appRoot | Out-Null
        Write-Step '6' 'Server tekshirilmoqda...'
        if (!(Wait-ForHealth $HealthTimeoutSeconds)) { throw 'Server health tekshiruvidan o‘tmadi.' }
    }
    if (!$NoRestart) { Start-Process -FilePath (Join-Path $appRoot 'RestaurantPOS.exe') -WorkingDirectory $appRoot | Out-Null }
    Write-Step '7' 'Yangilanish muvaffaqiyatli yakunlandi.'
    Write-Host "Backup: $backup"
} catch {
    $failure = $_
    Write-Host 'Yangilanish xatosi; oldingi dastur fayllari qaytarilmoqda...' -ForegroundColor Yellow
    $state = Get-Content -LiteralPath (Join-Path $backup 'files.json') -Raw | ConvertFrom-Json
    foreach ($entry in @($state)) {
        $current = Join-Path $installation $entry.Relative
        $old = Join-Path $backup $entry.Relative
        if ($entry.Existed) { Copy-ReleaseFile $old $current }
        elseif (Test-Path -LiteralPath $current -PathType Leaf) { Remove-Item -LiteralPath $current -Force }
    }
    throw $failure
} finally {
    foreach ($taskName in $tasks) { Enable-ScheduledTask -TaskName $taskName | Out-Null }
    if ($downloadRoot -and (Test-Path -LiteralPath $downloadRoot)) { Remove-Item -LiteralPath $downloadRoot -Recurse -Force }
}
