param(
    [Parameter(Mandatory=$true)][string]$InstallDirectory,
    [Parameter(Mandatory=$true)][ValidateSet('Server','Cashier')][string]$Mode,
    [string]$PostgresServiceName,
    [string]$ApiBaseUrl = 'http://127.0.0.1:8000'
)
$ErrorActionPreference = 'Stop'
try {
    $root = (Resolve-Path -LiteralPath $InstallDirectory).Path
    $binaryRoot = if (Test-Path -LiteralPath (Join-Path $root 'app\RestaurantPOS.exe')) { Join-Path $root 'app' } else { $root }
    if ($Mode -eq 'Server') {
        if (!$PostgresServiceName) { throw 'PostgreSQL service name is required.' }
        $ready = $false
        for ($attempt = 0; $attempt -lt 90; $attempt++) {
            if ((Get-Service -Name $PostgresServiceName).Status -eq 'Running') { $ready = $true; break }
            Start-Sleep -Seconds 2
        }
        if (!$ready) { throw 'PostgreSQL service did not start.' }
        $executable = Join-Path $binaryRoot 'RestaurantServer.exe'
    } else {
        $ready = $false
        for ($attempt = 0; $attempt -lt 90; $attempt++) {
            try {
                $health = Invoke-RestMethod -Uri ($ApiBaseUrl.TrimEnd('/') + '/health') -TimeoutSec 2
                if ($health.status -eq 'ok') { $ready = $true; break }
            } catch { }
            Start-Sleep -Seconds 2
        }
        if (!$ready) { throw 'Backend health check did not succeed.' }
        $executable = Join-Path $binaryRoot 'RestaurantPOS.exe'
    }
    # Synchronous process tracking lets Task Scheduler restart failed applications.
    $process = Start-Process -FilePath $executable -WorkingDirectory $binaryRoot -PassThru -Wait
    exit $process.ExitCode
} catch {
    # Do not output exception details or environment configuration.
    Write-Error 'Restaurant startup failed. Check the PostgreSQL service and backend health.'
    exit 1
}
