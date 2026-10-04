# Run on Windows with Python 3.12 x64. Output: dist/Monoblock1 and dist/Monoblock2.
$ErrorActionPreference = 'Stop'
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    & py -3.12 -m venv .venv-build
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 x64 is required.' }
    $python = Join-Path (Get-Location) '.venv-build\Scripts\python.exe'
    & $python -m pip install -r requirements.txt pyinstaller
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    Remove-Item Env:DEBUG -ErrorAction SilentlyContinue
    foreach ($spec in @('pos.spec', 'admin.spec', 'server.spec', 'bootstrap_admin.spec')) {
        & $python -m PyInstaller --noconfirm --clean $spec
        if ($LASTEXITCODE -ne 0) { throw "Build failed: $spec" }
    }
    $hashes = @{}
    foreach ($name in @('RestaurantPOS.exe', 'RestaurantAdmin.exe', 'RestaurantServer.exe')) {
        $hashes[$name] = (Get-FileHash "dist/$name" -Algorithm SHA256).Hash
    }
    $hashes | ConvertTo-Json | Set-Content dist/SHA256.json -Encoding UTF8
    foreach ($terminal in @(1, 2)) {
        $root = "dist/Monoblock$terminal/RestaurantPOS"
        foreach ($folder in @('app', 'scripts', 'config', 'logs', 'media', 'backups')) {
            New-Item -ItemType Directory -Path "$root/$folder" -Force | Out-Null
        }
        # Both packages include the server binary for compatibility with the existing updater;
        # Monoblock2's server=false prevents backend startup and migrations.
        foreach ($name in @('RestaurantPOS.exe', 'RestaurantAdmin.exe', 'RestaurantServer.exe', 'SHA256.json')) {
            Copy-Item "dist/$name" "$root/app/" -Force
        }
        foreach ($name in @('update_windows.ps1', 'start-runtime.ps1', 'install_autostart_windows.ps1', 'test-deployment.ps1', 'cleanup_client_transactions.ps1')) {
            Copy-Item "scripts/$name" "$root/scripts/" -Force
        }
        $version = Get-Content version.json -Raw | ConvertFrom-Json
        $version.server = ($terminal -eq 1)
        $version | ConvertTo-Json | Set-Content "$root/version.json" -Encoding UTF8
        Set-Content "$root/config/README.txt" 'Keep the existing .env. M1: local backend; M2: POS_API_BASE_URL=http://M1_LAN_IP:8000'
        Compress-Archive -Path $root -DestinationPath "dist/RestaurantPOS-Monoblock$terminal.zip" -Force
    }
    Write-Host 'Ready: dist/RestaurantPOS-Monoblock1.zip and dist/RestaurantPOS-Monoblock2.zip'
} finally {
    Pop-Location
}
