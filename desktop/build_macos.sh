#!/usr/bin/env bash
# Build do aplicativo macOS (.app) — repetível.
#
# Uso (a partir da pasta desktop/):
#   ./build_macos.sh
#
# Pré-requisitos (rodar num Mac — o PyInstaller não faz cross-compile):
#   - Python 3.12+ instalado
#   - bin/ffmpeg e bin/ffprobe presentes (versões macOS do FFmpeg)
#
# Resultado: dist/Project Codename.app
# Empacotamento em .dmg é feito separadamente (ver distribuicao/).

set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"

echo "==> Instalando dependencias (requirements.txt)..."
"$PYTHON" -m pip install -r requirements.txt

for bin in bin/ffmpeg bin/ffprobe; do
    if [ ! -f "$bin" ]; then
        echo "Binario ausente: $bin. Coloque as versoes macOS do FFmpeg em desktop/bin/ antes de buildar." >&2
        exit 1
    fi
done

echo "==> Gerando o .app com PyInstaller..."
"$PYTHON" -m PyInstaller --clean --noconfirm build.spec

echo "==> Pronto: dist/Project Codename.app"
