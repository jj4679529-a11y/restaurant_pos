[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory=$true)][string]$InstallDirectory,
    [switch]$Server,
    [string]$PostgresServiceName,
    [string]$ApiBaseUrl = 'http://127.0.0.1:8000'
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath $InstallDirectory).Path
$binaryRoot = if (Test-Path -LiteralPath (Join-Path $root 'app\RestaurantPOS.exe')) { Join-Path $root 'app' } else { $root }
$launcher = Join-Path $PSScriptRoot 'start-runtime.ps1'
if (!(Test-Path -LiteralPath $launcher)) { throw 'Missing start-runtime.ps1 beside installer.' }
if ($root.Contains('"') -or $ApiBaseUrl.Contains('"') -or ([string]$PostgresServiceName).Contains('"')) { throw 'Invalid argument.' }
$user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$executables = @('RestaurantPOS.exe')
if ($Server) { $executables += 'RestaurantServer.exe' }
foreach ($name in $executables) {
    $path = Join-Path $binaryRoot $name
    if (!(Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing $name" }
}
if ($Server) {
    if (!$PostgresServiceName) {
        $matches = @(Get-CimInstance Win32_Service | Where-Object { $_.PathName -match '(?i)(pg_ctl|postgres)\.exe' })
        if ($matches.Count -ne 1) { throw 'Specify the exact PostgreSQL service with -PostgresServiceName.' }
        $PostgresServiceName = $matches[0].Name
    }
    $service = Get-CimInstance Win32_Service | Where-Object { $_.Name -eq $PostgresServiceName }
    if (!$service -or $service.PathName -notmatch '(?i)(pg_ctl|postgres)\.exe') { throw 'Not a verified PostgreSQL service.' }
    if ($PSCmdlet.ShouldProcess($PostgresServiceName, 'Set PostgreSQL automatic service startup')) {
        Set-Service -Name $PostgresServiceName -StartupType Automatic
        Start-Service -Name $PostgresServiceName
    }
}
foreach ($name in $executables) {
    $taskName = if ($name -eq 'RestaurantServer.exe') { 'RestaurantPOS-Server' } else { 'RestaurantPOS-Cashier' }
    $existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    $path = Join-Path $binaryRoot $name
    if ($existing -and @($existing.Actions)[0].WorkingDirectory -ne $root) { throw "Existing $taskName belongs to another installation." }
    if ($PSCmdlet.ShouldProcess($path, 'Register per-user logon task with failure restart')) {
        $mode = if ($name -eq 'RestaurantServer.exe') { 'Server' } else { 'Cashier' }
        $arguments = '-NoProfile -NonInteractive -ExecutionPolicy RemoteSigned -File "{0}" -InstallDirectory "{1}" -Mode {2} -ApiBaseUrl "{3}"' -f $launcher, $root, $mode, $ApiBaseUrl
        if ($Server) { $arguments += ' -PostgresServiceName "{0}"' -f $PostgresServiceName }
        $action = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -Argument $arguments -WorkingDirectory $root
        $trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
        $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
        $settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -StartWhenAvailable
        Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
    }
}

# Per-user launchers make the two desktop applications available without opening
# installation folders. They are shortcuts only; no credentials/configuration is copied.
$shortcutTargets = @{
    'Restaurant POS.lnk' = Join-Path $binaryRoot 'RestaurantPOS.exe'
    'Restaurant Admin.lnk' = Join-Path $binaryRoot 'RestaurantAdmin.exe'
}
$desktop = [Environment]::GetFolderPath([Environment+SpecialFolder]::DesktopDirectory)
$startMenu = Join-Path ([Environment]::GetFolderPath([Environment+SpecialFolder]::StartMenu)) 'Programs\Restaurant POS'
foreach ($directory in @($desktop, $startMenu)) {
    if (!(Test-Path -LiteralPath $directory) -and $PSCmdlet.ShouldProcess($directory, 'Create per-user shortcut directory')) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }
}
if ($PSCmdlet.ShouldProcess('Restaurant POS desktop and Start Menu shortcuts', 'Create or update per-user launchers')) {
    $shell = New-Object -ComObject WScript.Shell
    foreach ($entry in $shortcutTargets.GetEnumerator()) {
        if (!(Test-Path -LiteralPath $entry.Value -PathType Leaf)) { throw "Missing executable for shortcut: $($entry.Value)" }
        foreach ($directory in @($desktop, $startMenu)) {
            $shortcut = $shell.CreateShortcut((Join-Path $directory $entry.Key))
            $shortcut.TargetPath = $entry.Value
            $shortcut.WorkingDirectory = $binaryRoot
            $shortcut.IconLocation = $entry.Value
            $shortcut.Save()
        }
    }
}
if ($Server -and !(Get-NetFirewallRule -Name 'RestaurantPOS-API-Private' -ErrorAction SilentlyContinue)) {
    if ($PSCmdlet.ShouldProcess('TCP 8000 / Private / LocalSubnet', 'Create API-only firewall rule')) {
        New-NetFirewallRule -Name 'RestaurantPOS-API-Private' -DisplayName 'Restaurant POS API (Private LAN)' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8000 -Profile Private -RemoteAddress LocalSubnet | Out-Null
    }
}
Write-Host 'Configured login startup and per-user POS/Admin shortcuts. No PostgreSQL LAN rule was added. Use AUTO_START_WITH_WINDOWS=false to avoid duplicate Run-key startup.'
