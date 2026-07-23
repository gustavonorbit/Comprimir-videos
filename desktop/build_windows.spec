# -*- mode: python ; coding: utf-8 -*-
"""
Spec do PyInstaller para o app Desktop no Windows.

Gera um único executável (.exe) autocontido, com FFmpeg/FFprobe embutidos,
equivalente ao build de macOS definido em build.spec (que gera o .app).

Nome temporário: o projeto ainda não tem nome definitivo (ver README > Escolha do Nome).
"""

from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

SPEC_DIR = Path(SPECPATH)

APP_NAME = "Project Codename"

datas = collect_data_files("customtkinter")

# Binários do FFmpeg para Windows (versões .exe embutidas no bundle).
binaries = [
    (str(SPEC_DIR / "bin" / "ffmpeg.exe"), "bin"),
    (str(SPEC_DIR / "bin" / "ffprobe.exe"), "bin"),
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

# --onefile: empacota tudo num único .exe (o compressor.py resolve os binários
# a partir de sys._MEIPASS/bin em tempo de execução).
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(SPEC_DIR / "assets" / "icon.ico"),
)
