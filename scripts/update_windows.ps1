[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory=$true)][string]$InstallDirectory,
    [Parameter(Mandatory=$true)][string]$ReleaseDirectory,
    [switch]$Server
)
$ErrorActionPreference = 'Stop'
$target = (Resolve-Path -LiteralPath $InstallDirectory).Path
$source = (Resolve-Path -LiteralPath $ReleaseDirectory).Path
if ($target -eq $source) { throw 'Release and installation folders must differ.' }
$installation = $target
if (Test-Path -LiteralPath (Join-Path $target 'app\RestaurantPOS.exe')) { $target = Join-Path $target 'app' }
if (Test-Path -LiteralPath (Join-Path $source 'app\RestaurantPOS.exe')) { $source = Join-Path $source 'app' }
if ($target -eq $source) { throw 'Release and installation binary folders must differ.' }
# Strict allowlist: never copy/delete .env, media, PostgreSQL data, or configuration.
$names = @('RestaurantServer.exe', 'RestaurantPOS.exe', 'RestaurantAdmin.exe')
$manifest = Get-Content -LiteralPath (Join-Path $source 'SHA256.json') -Raw | ConvertFrom-Json
foreach ($name in $names) {
    $file = Join-Path $source $name
    if (!(Test-Path -LiteralPath $file -PathType Leaf)) { throw "Missing $name" }
    if (!$manifest.$name -or (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash -ne $manifest.$name) { throw "Hash mismatch: $name" }
    if (Test-Path -LiteralPath (Join-Path $target $name)) {
        if ((Get-Item -LiteralPath (Join-Path $target $name)).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Refusing linked executable target.' }
    }
}
if (!$PSCmdlet.ShouldProcess($target, 'Back up and replace only application executables; apply forward migrations on server')) { return }
$backup = Join-Path $target ('binary-backups\' + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $backup | Out-Null
$tasks = @()
try {
    foreach ($taskName in @('RestaurantPOS-Server', 'RestaurantPOS-Cashier')) {
        $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        $action = if ($task) { @($task.Actions)[0] } else { $null }
        if ($action -and ($action.WorkingDirectory -eq $installation -or (Split-Path -Parent $action.Execute) -eq $target) -and $task.State -ne 'Disabled') {
            Disable-ScheduledTask -TaskName $taskName | Out-Null
            $tasks += $taskName
        }
    }
    # Refuse running applications: cashier must finish transactions and close them first.
    foreach ($process in Get-Process) {
        if ($process.Path -and $names -contains (Split-Path -Leaf $process.Path) -and (Split-Path -Parent $process.Path) -eq $target) {
            throw 'Close POS/Admin/Server in this installation before updating. No process was killed.'
        }
    }
    foreach ($name in $names) {
        $current = Join-Path $target $name
        if (Test-Path -LiteralPath $current) { Copy-Item -LiteralPath $current -Destination (Join-Path $backup $name) }
    }
    foreach ($name in $names) { Copy-Item -LiteralPath (Join-Path $source $name) -Destination (Join-Path $target $name) -Force }
    if ($Server) {
        & (Join-Path $target 'RestaurantServer.exe') --migrate
        if ($LASTEXITCODE -ne 0) { throw 'Migration failed; inspect configuration before retrying.' }
    }
    Write-Host "Update complete. Binary backup: $backup. Database, .env and media preserved. Start POS when ready."
} catch {
    foreach ($name in $names) {
        $old = Join-Path $backup $name
        if (Test-Path -LiteralPath $old) { Copy-Item -LiteralPath $old -Destination (Join-Path $target $name) -Force }
    }
    throw
} finally {
    foreach ($taskName in $tasks) { Enable-ScheduledTask -TaskName $taskName | Out-Null }
}
