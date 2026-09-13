# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['admin.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'app.ui.dialogs.catalog_dialogs',
        'app.ui.dialogs.volume_dialog',
        'app.ui.dialogs.saved_orders',
        'app.ui.dialogs.product_dialog',
        'app.ui.dialogs.number_dialog',
        'app.ui.widgets.cart_widget',
        'app.ui.widgets.product_card',
        'app.ui.checkout',
        'app.ui.admin.admin_window',
        'app.ui.admin.api',
        'app.ui.admin.pages',
        'app.ui.admin.forms',
        'app.ui.admin.menu_settings',
        'PySide6.QtWebEngineCore',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='RestaurantAdmin',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
