#!/usr/bin/env bash
# Build do aplicativo macOS (.app) — repetível.
#
# Uso (a partir da pasta desktop/):
#   ./build_macos.sh
#
# Pré-requisitos (rodar num Mac — o PyInstaller não faz cross-compile):
#   - Python 3.12+ instalado
#
# Os binários do FFmpeg NAO sao versionados no git (grandes demais para o
# GitHub). Este script os baixa via tools/fetch_ffmpeg.py, conferindo o SHA-256
# fixado em tools/ffmpeg_manifest.json, e valida que sao estaticos e universais
# antes de empacotar. Para pular o download (ex.: build offline com os binarios
# ja em bin/), use SKIP_FFMPEG_FETCH=1 — a validacao roda mesmo assim.
#
# Resultado: dist/Project Codename.app
# Empacotamento em .dmg é feito separadamente (ver distribuicao/).

set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"

echo "==> Instalando dependencias (requirements.txt)..."
"$PYTHON" -m pip install -r requirements.txt

if [ "${SKIP_FFMPEG_FETCH:-0}" = "1" ]; then
    echo "==> Validando FFmpeg embutido (download pulado)..."
    "$PYTHON" tools/fetch_ffmpeg.py --check
else
    echo "==> Baixando e validando FFmpeg embutido..."
    "$PYTHON" tools/fetch_ffmpeg.py
fi

echo "==> Rodando os testes do binario embutido..."
"$PYTHON" -m unittest tests.test_bundled_ffmpeg

echo "==> Gerando o .app com PyInstaller..."
"$PYTHON" -m PyInstaller --clean --noconfirm build.spec

echo "==> Pronto: dist/Project Codename.app"
