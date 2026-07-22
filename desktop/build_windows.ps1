# Build do executável Windows (.exe) — repetível.
#
# Uso (a partir da pasta desktop/):
#   powershell -ExecutionPolicy Bypass -File .\build_windows.ps1
#
# Pré-requisitos:
#   - Python 3.12+ instalado
#   - bin\ffmpeg.exe e bin\ffprobe.exe presentes (versões Windows do FFmpeg)
#
# Resultado: dist\Project Codename.exe (único arquivo, FFmpeg embutido).

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Localiza o Python (usa 'py' launcher se existir, senão 'python').
$python = if (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { "python" }

Write-Host "==> Instalando dependencias (requirements.txt)..."
& $python -m pip install -r requirements.txt

foreach ($bin in @("bin\ffmpeg.exe", "bin\ffprobe.exe")) {
    if (-not (Test-Path $bin)) {
        throw "Binario ausente: $bin. Coloque as versoes Windows do FFmpeg em desktop\bin\ antes de buildar."
    }
}

Write-Host "==> Gerando o .exe com PyInstaller..."
& $python -m PyInstaller --clean --noconfirm build_windows.spec

Write-Host "==> Pronto: dist\Project Codename.exe"
