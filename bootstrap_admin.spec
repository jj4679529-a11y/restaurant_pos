# Console-only one-file bootstrap; never bundle deployment .env files.
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = collect_all("psycopg")
a = Analysis(
    ["bootstrap_admin.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=[*hiddenimports, "psycopg2", "sqlalchemy.dialects.postgresql.psycopg",
                   "sqlalchemy.dialects.postgresql.psycopg2", "pwdlib.hashers.argon2"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["PySide6"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="RestaurantBootstrapAdmin",
    console=True,
    debug=False,
    strip=False,
    upx=True,
)
