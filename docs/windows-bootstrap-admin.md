# Create the first Windows POS admin

Download the `windows-executables` artifact from a successful Windows build on
`phase-13-two-monoblock`. Extract `RestaurantBootstrapAdmin.exe` beside the other
executables. No Python installation or source files are required on the monoblock.

This console tool requires **DATABASE_URL in the process environment**; it does
not use an adjacent `.env` as a substitute for that requirement. Use the same
database URL as the working server. It must target PostgreSQL `restaurant_pos`.

Open PowerShell in the deployment folder and run:

```powershell
# Paste the working server's complete DATABASE_URL at the hidden prompt.
# Reserved characters in the URL password must already be percent-encoded.
$secureUrl = Read-Host "Working server DATABASE_URL" -AsSecureString
$urlPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureUrl)
$previousUrl = $env:DATABASE_URL
$previousDebug = $env:DEBUG
try {
    $env:DATABASE_URL = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($urlPointer)
    $env:DEBUG = "false"
    & .\RestaurantBootstrapAdmin.exe
    if ($LASTEXITCODE -ne 0) { throw "Bootstrap failed; see the message above." }
} finally {
    $env:DATABASE_URL = $previousUrl
    $env:DEBUG = $previousDebug
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($urlPointer)
    $secureUrl.Dispose()
}
```

The URL is held in runtime memory only, not printed or saved in shell history.
Example format (placeholders only):
`postgresql+psycopg://postgres:<URL_ENCODED_PASSWORD>@localhost:5432/restaurant_pos`.

At the two hidden prompts, enter a **new POS admin password**, not the database
password. On success the tool prints exactly:

```text
Admin created successfully. Username: admin
```

Log in to POS/Admin with `admin` and the password just entered. Do not put that
password in `.env`, source code, Git, or a command-line argument.

If any ADMIN already exists (including an inactive ADMIN), the tool exits without
changes. It also refuses an occupied `admin` username. This is not a password-reset
tool. Creation uses the existing seed service and production Argon2 hash, in one
transaction with a locked re-check. No full seed, migrations, menu/settings writes,
or database creation/deletion are performed.

The Windows CI smoke test invokes `--self-test` with a nonconnecting test URL to
check packaged imports, both PostgreSQL drivers, and production hashing. It does
not create a user or replace a real Windows/PostgreSQL acceptance test.
