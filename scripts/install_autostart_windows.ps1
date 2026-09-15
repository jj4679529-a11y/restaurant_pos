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
if ($Server -and !(Get-NetFirewallRule -Name 'RestaurantPOS-API-Private' -ErrorAction SilentlyContinue)) {
    if ($PSCmdlet.ShouldProcess('TCP 8000 / Private / LocalSubnet', 'Create API-only firewall rule')) {
        New-NetFirewallRule -Name 'RestaurantPOS-API-Private' -DisplayName 'Restaurant POS API (Private LAN)' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8000 -Profile Private -RemoteAddress LocalSubnet | Out-Null
    }
}
Write-Host 'Configured login startup. No PostgreSQL LAN rule was added. Use AUTO_START_WITH_WINDOWS=false to avoid duplicate Run-key startup.'
