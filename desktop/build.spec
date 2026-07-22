# -*- mode: python ; coding: utf-8 -*-
"""
Spec do PyInstaller para o app Desktop.
Nome temporário: o projeto ainda não tem nome definitivo (ver README > Escolha do Nome).
"""

from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

SPEC_DIR = Path(SPECPATH)

APP_NAME = "Project Codename"
APP_VERSION = "0.1.0-beta"
BUNDLE_ID = "org.projectcodename.desktop"

datas = collect_data_files("customtkinter")

binaries = [
    (str(SPEC_DIR / "bin" / "ffmpeg"), "bin"),
    (str(SPEC_DIR / "bin" / "ffprobe"), "bin"),
]

a = Analysis(
    [str(SPEC_DIR / "main.py")],
    pathex=[str(SPEC_DIR)],
    binaries=binaries,
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)

app = BUNDLE(
    coll,
    name=f"{APP_NAME}.app",
    icon=str(SPEC_DIR / "assets" / "icon.icns"),
    bundle_identifier=BUNDLE_ID,
    info_plist={
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": APP_NAME,
        "CFBundleShortVersionString": APP_VERSION,
        "CFBundleVersion": APP_VERSION,
        "NSHighResolutionCapable": True,
        "NSHumanReadableCopyright": "GPL-3.0",
    },
)
