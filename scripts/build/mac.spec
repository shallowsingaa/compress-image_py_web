# -*- mode: python ; coding: utf-8 -*-
block_cipher = None

a = Analysis(
    ['../../main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['PIL', 'packaging', 'colorama'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.binaries, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='compress-image',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    preferred_encoding='UTF-8',
)