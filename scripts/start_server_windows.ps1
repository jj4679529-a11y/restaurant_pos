$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $pythonExe)) { throw 'Create .venv and install requirements.txt first.' }
$previousDebug = $env:DEBUG
Push-Location $projectRoot
try {
    Remove-Item Env:DEBUG -ErrorAction SilentlyContinue
    & $pythonExe -m uvicorn main:app --host 0.0.0.0 --port 8000
    $serverExitCode = $LASTEXITCODE
} finally {
    $env:DEBUG = $previousDebug
    Pop-Location
}
exit $serverExitCode
