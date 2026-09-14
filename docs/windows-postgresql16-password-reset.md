# Windows PostgreSQL 16 authentication recovery

This runbook is prepared from the repository, not executed on a Windows machine.
Do not reset a password until the service, port and configuration paths below are
confirmed. No application code, migrations or existing database contents change.
Stop RestaurantServer.exe and pause both cashiers during the maintenance window.
Restarting PostgreSQL disconnects other database clients too.

## Findings from this checkout

- `.github/workflows/build-windows.yml:17-18` specifies the `postgres` role and
  password `po***es` for an ephemeral **Ubuntu CI PostgreSQL 14 container**.
- The matching CI DATABASE_URL is at line 47. The Windows build is a separate job;
  this does not provision or reset the password on a Windows PostgreSQL installation.
- `.env:4` uses a local Mac role, `boysafarnurmatov`, with **no password** in the URL,
  database `restaurant_pos`. `.env.save:4` also has no database password and uses
  database `restaurantpos`. These are not Windows `postgres` credentials.
- `.env.example:2` and `docs/windows-exe-build.md:71` contain USER/PASSWORD placeholders.
- No Windows PostgreSQL installer password, POSTGRES_PASSWORD installation setting,
  or other usable Windows database credential was found in the checkout's text files,
  including ignored env files, setup scripts, workflows and local worktree copies.
  Binary artifacts, OS credential stores and the actual Windows filesystem were not
  searched. A username/password for the POS application is not a PostgreSQL password.
- `app/core/config.py:9-20` reads `.env` next to the executable in frozen mode.
  Process environment variables take precedence. `server.spec` does not bundle `.env`.

The CI password is not evidence of the Windows password. PostgreSQL stores a password
verifier rather than a recoverable plaintext password; absent a password-manager or
installation record, reset it instead of attempting to recover it from the database.

## 1. Read-only discovery (Administrator PowerShell on Monoblock 1)

Do not paste `.env`, passwords, or full DATABASE_URL values into chat or logs.

```powershell
$ErrorActionPreference = 'Stop'
$services = @(Get-CimInstance Win32_Service | Where-Object {
    $_.PathName -match '(?i)(pg_ctl|postgres)\.exe'
})
$services | Select-Object Name, State, ProcessId, PathName | Format-List
$serviceName = Read-Host 'Exact PostgreSQL 16 service Name from the list'
$pgService = @($services | Where-Object Name -eq $serviceName)
if ($pgService.Count -ne 1 -or $pgService[0].State -ne 'Running') {
    throw 'Select exactly one RUNNING PostgreSQL service; do not guess.'
}
$pgService = $pgService[0]
$serviceCommand = $pgService.PathName

# Fail closed for custom server options. These require reviewing the actual
# startup options; -C alone does not account for a running server's overrides.
if ($serviceCommand -match '(?i)(?:^|\s)"?(?:-o|-c|--config[-_]file)(?:\s|=|"|$)') {
    throw 'Custom service options detected. Review these before editing any HBA file.'
}
$exeMatch = [regex]::Match($serviceCommand, '^\s*(?:"([^"]+\.exe)"|(\S+\.exe))')
$directoryMatch = [regex]::Match($serviceCommand, '(?:^|\s)"?-D"?\s+(?:"([^"]+)"|(\S+))')
if (-not $exeMatch.Success -or -not $directoryMatch.Success) {
    throw 'Cannot safely determine executable and -D directory from this service.'
}
$serviceExe = ($exeMatch.Groups[1].Value + $exeMatch.Groups[2].Value)
$configDirectory = ($directoryMatch.Groups[1].Value + $directoryMatch.Groups[2].Value)
$binDirectory = Split-Path -Parent $serviceExe
$postgresExe = Join-Path $binDirectory 'postgres.exe'
$psqlExe = Join-Path $binDirectory 'psql.exe'
if ((& $postgresExe --version) -notmatch 'PostgreSQL\) 16\.') {
    throw 'This is not the requested PostgreSQL 16 installation.'
}
function Read-PgSetting([string]$setting) {
    $output = & $postgresExe -D $configDirectory -C $setting
    if ($LASTEXITCODE -ne 0) { throw "Cannot resolve PostgreSQL setting: $setting" }
    return ($output -join "`n").Trim()
}
$dataDirectory = Read-PgSetting 'data_directory'
$hbaFile = Read-PgSetting 'hba_file'
$configFile = Read-PgSetting 'config_file'
$pgPort = [int](Read-PgSetting 'port')
foreach ($path in @($dataDirectory, $hbaFile, $configFile)) {
    if (-not [IO.Path]::IsPathRooted($path) -or -not (Test-Path -LiteralPath $path)) {
        throw 'Unresolved/relative configuration path: stop rather than guess.'
    }
}
$serverPid = [int](Get-Content -LiteralPath (Join-Path $dataDirectory 'postmaster.pid') -TotalCount 1)
$serverProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$serverPid"
if (-not $serverProcess -or $serverProcess.Name -ne 'postgres.exe' -or
    ($serverProcess.ParentProcessId -ne $pgService.ProcessId -and $serverPid -ne $pgService.ProcessId)) {
    throw 'Data directory PID does not match this service. Stop.'
}
if (-not $serverProcess.CommandLine -or
    $serverProcess.CommandLine -match '(?:^|\s)"?(?:-c|-p|-h|--[^\s"]+)(?:\s|=|"|$)') {
    throw 'Running server has custom/unknown startup options. Resolve them before continuing.'
}
$runtimeD = [regex]::Match($serverProcess.CommandLine, '(?:^|\s)"?-D"?\s+(?:"([^"]+)"|(\S+))')
if (-not $runtimeD.Success -or
    (Resolve-Path -LiteralPath ($runtimeD.Groups[1].Value + $runtimeD.Groups[2].Value)).Path -ne
    (Resolve-Path -LiteralPath $configDirectory).Path) {
    throw 'Running server -D differs from selected service. Stop.'
}
if ($pgPort -ne 5432) { throw 'Selected service is not the port 5432 instance from the reported error.' }
Get-NetTCPConnection -State Listen -LocalPort $pgPort | Select-Object LocalAddress, LocalPort, OwningProcess
[pscustomobject]@{Service=$serviceName; Data=$dataDirectory; Config=$configFile; HBA=$hbaFile; Port=$pgPort} | Format-List
```

If discovery stops, send the service name/path and error for review; **do not fall
back to editing a guessed `C:\Program Files\PostgreSQL\16\data\pg_hba.conf`**.
For custom installations, run `postgres -C` with the same server options, or use an
existing authorized connection to `SHOW data_directory; SHOW config_file; SHOW hba_file;`.

## 2. Try the known installation password first

```powershell
& $psqlExe -X -h 127.0.0.1 -p $pgPort -U postgres -d postgres -W -c 'SELECT current_user, version(); SHOW hba_file; SHOW data_directory;'
```

Enter the password at the hidden prompt. If this succeeds, **skip the reset**: fix
the executable's .env/overriding environment variable and URL encoding in section 5.
If it fails and no installation password is available, continue locally below.

## 3. Temporary localhost-only reset, with immediate restoration

Use the SAME elevated PowerShell session so the validated variables remain defined.
No untrusted local users/processes should run during this short window: temporary
trust lets a local process assume the postgres role for the postgres database.
There is no LAN trust rule, no firewall change, no 5432 exposure and no data deletion.
Do not close PowerShell or reboot during this block. `finally` cannot protect against
power loss; the backup path is printed for emergency manual restoration.

```powershell
$backup = $hbaFile + '.before-password-reset-' + [guid]::NewGuid().ToString('N') + '.bak'
Copy-Item -LiteralPath $hbaFile -Destination $backup -ErrorAction Stop
$originalHash = (Get-FileHash -LiteralPath $hbaFile -Algorithm SHA256).Hash
if ((Get-FileHash -LiteralPath $backup -Algorithm SHA256).Hash -ne $originalHash) {
    throw 'HBA backup verification failed.'
}
Write-Host "HBA recovery backup: $backup"
$originalText = [IO.File]::ReadAllText($hbaFile)
$temporaryRules = "host postgres postgres 127.0.0.1/32 trust`r`nhost postgres postgres ::1/128 trust`r`n"
try {
    # Rules must precede earlier matching password/reject rules.
    [IO.File]::WriteAllText($hbaFile, $temporaryRules + $originalText, [Text.UTF8Encoding]::new($false))
    Restart-Service -Name $serviceName -ErrorAction Stop
    (Get-Service -Name $serviceName).WaitForStatus('Running', [TimeSpan]::FromSeconds(30))
    # Safest password change: hidden prompt, client-side encryption, no plaintext
    # password in shell history, command arguments, SQL files or server logs.
    & $psqlExe -X -h 127.0.0.1 -p $pgPort -U postgres -d postgres -w -v ON_ERROR_STOP=1 -c '\password postgres'
    if ($LASTEXITCODE -ne 0) { throw 'Password change failed; HBA will still be restored.' }
} finally {
    try {
        Copy-Item -LiteralPath $backup -Destination $hbaFile -Force -ErrorAction Stop
        if ((Get-FileHash -LiteralPath $hbaFile -Algorithm SHA256).Hash -ne $originalHash) {
            throw 'Restored HBA differs from its original backup.'
        }
        Restart-Service -Name $serviceName -ErrorAction Stop
        (Get-Service -Name $serviceName).WaitForStatus('Running', [TimeSpan]::FromSeconds(30))
    } catch {
        # Fail closed rather than intentionally leave the temporary trust running.
        Stop-Service -Name $serviceName -ErrorAction SilentlyContinue
        throw "HBA restoration/restart failed. Restore $backup to $hbaFile before starting $serviceName."
    }
}
```

The SQL requested is:

```sql
ALTER USER postgres WITH PASSWORD '<NEW_PASSWORD>';
```

`ALTER USER` is an alias for `ALTER ROLE`. The recommended `\password postgres`
above performs that password change using an encrypted verifier, without putting
the new plaintext password in SQL history/logs. Do not put a real password into this
document or a committed script.

If you specifically must execute the literal ALTER USER form, replace ONLY the psql
invocation inside the try block with an interactive `psql -X ... -w` session, run
the statement locally, then `\q` immediately so finally restores authentication.
Set `$env:PSQL_HISTORY='NUL'` before entering that session and review/disable SQL
statement/audit logging for the maintenance session first. Literal SQL may expose
the password in terminal display or server/audit logs; `\password` is safer.

Emergency restoration if the PowerShell session is lost: identify the recorded
backup and service, copy the backup over the exact original HBA file, then restart
that service. Do not remove the backup until restoration and authentication pass.

## 4. Verify password authentication and database

After the original HBA is restored:

```powershell
& $psqlExe -X -h 127.0.0.1 -p $pgPort -U postgres -d postgres -W -v ON_ERROR_STOP=1
```

Enter the NEW password at the prompt. In psql:

```sql
SELECT current_user, inet_server_addr(), inet_server_port();
SHOW hba_file;
SELECT line_number, type, database, user_name, address, auth_method, error
FROM pg_hba_file_rules ORDER BY rule_number;
SELECT datname FROM pg_database WHERE datname = 'restaurant_pos';
SELECT 'CREATE DATABASE restaurant_pos OWNER postgres'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'restaurant_pos')
\gexec
\connect restaurant_pos postgres 127.0.0.1 5432
SELECT current_database();
\q
```

The conditional command creates only a missing empty database; it never drops or
replaces an existing one. It does not create application tables or run migrations.
If the database was missing but existing restaurant data was expected, stop and
locate the correct instance/backup before proceeding operationally.

Inspect the first matching HBA rule: it must require password authentication
(`scram-sha-256`, or an existing compatible `md5` rule), not trust. `-W` forces a
prompt but by itself does NOT prove the server required a password. If the original
HBA already had trust, stop and review that preexisting policy separately.
Do not leave any password-reset trust entries behind. Test `::1` separately if you
intend to keep `localhost` in the URL and the server listens on IPv6.

## 5. Correct executable config without exposing secrets

Find the actual executable location in Explorer. Keep `.env` beside it, not inside
PyInstaller's temporary extraction directory. Windows Explorer must show file
extensions so the filename is `.env`, not `.env.txt`. Preserve existing settings,
especially JWT_SECRET_KEY; do not overwrite it merely to reset a database password.

Safe template (placeholders only; NOT usable until replaced locally):

```dotenv
DATABASE_URL=postgresql+psycopg://postgres:<URL_ENCODED_NEW_PASSWORD>@127.0.0.1:5432/restaurant_pos
APP_NAME="Restaurant POS"
APP_ENV=production
DEBUG=false
JWT_SECRET_KEY=<EXISTING_SERVER_JWT_SECRET>
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=720
```

Use `postgresql+psycopg` for the psycopg 3 executable described in this incident.
Password characters such as @, :, /, #, %, ? must be percent-encoded in the URL.
Enter the original, unencoded password at psql prompts. A password that works in
psql but fails in the app usually points to URL encoding, the wrong .env, a stale
environment override, a different user/port, or a different instance.

Report ONLY whether overrides exist, never their values:

```powershell
foreach ($scope in 'Process','User','Machine') {
    $present = -not [string]::IsNullOrEmpty([Environment]::GetEnvironmentVariable('DATABASE_URL', $scope))
    Write-Host "$scope DATABASE_URL present: $present"
}
```

To launch from a shell using the adjacent .env rather than that shell's stale URL:

```powershell
$serverExe = (Resolve-Path -LiteralPath (Read-Host 'Full path to RestaurantServer.exe')).Path
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
Remove-Item Env:DEBUG -ErrorAction SilentlyContinue
& $serverExe
```

This clears only current-process overrides, not permanent User/Machine settings.
Fix those privately if set, or future Explorer/service launches may inherit them.
Fully restart RestaurantServer.exe after a config change (settings are cached).
From another terminal, verify `/health` and then actual login/catalog/database
operations; health alone is not proof of correct database authentication.

References: [PostgreSQL 16 file locations](https://www.postgresql.org/docs/16/runtime-config-file-locations.html),
[postgres -C limitation](https://www.postgresql.org/docs/16/app-postgres.html),
[HBA first-match rules](https://www.postgresql.org/docs/16/auth-pg-hba-conf.html),
[psql password command](https://www.postgresql.org/docs/16/app-psql.html),
[ALTER USER alias](https://www.postgresql.org/docs/16/sql-alteruser.html).
