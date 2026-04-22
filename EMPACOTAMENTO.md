# 📦 GUIA DE EMPACOTAMENTO COM PyInstaller

## Objetivo
Transformar o programa Python em um executável independente (.exe no Windows, .app no macOS, binário no Linux).

---

## ⚠️ IMPORTANTE: Dependências Externas

**FFmpeg não será incluído no executável.** Os usuários finais precisarão ter FFmpeg instalado.

- O programa verifica automaticamente se FFmpeg está disponível
- Mostra instruções claras se não estiver instalado
- Isso reduz o tamanho do executável de ~500MB para ~50MB

---

## 📋 Pré-requisitos

### 1. Você já tem:
- Python 3.8+
- Projeto completo em: `/Users/gustavo/Comprimir videos/`
- Todas as dependências instaladas

### 2. Instalar PyInstaller
```bash
/usr/local/bin/python3 -m pip install pyinstaller
```

### 3. Verificar instalação
```bash
pyinstaller --version
# Deve mostrar: 6.x.x ou superior
```

---

## 🎯 PARA macOS

### Método 1: Simples (recomendado)
```bash
cd "/Users/gustavo/Comprimir videos"

pyinstaller \
  --onefile \
  --windowed \
  --name "Compressor de Vídeos" \
  --icon=icon.icns \
  main.py
```

**Resultado**: `dist/Compressor de Vídeos.app`

### Método 2: Com mais otimizações
```bash
pyinstaller \
  --onefile \
  --windowed \
  --name "Compressor de Vídeos" \
  --add-data "compressor.py:." \
  --add-data "ui.py:." \
  --hidden-import=customtkinter \
  --strip \
  --disable-windowed-traceback \
  main.py
```

### Executar o app:
```bash
open dist/"Compressor de Vídeos.app"
```

---

## 🪟 PARA Windows

### Método 1: Simples (recomendado)
```cmd
cd "C:\Caminho\Para\Comprimir videos"

pyinstaller ^
  --onefile ^
  --windowed ^
  --name "Compressor de Vídeos" ^
  --icon=icon.ico ^
  main.py
```

**Resultado**: `dist\Compressor de Vídeos.exe`

### Método 2: Com ícone e console minimizado
```cmd
pyinstaller ^
  --onefile ^
  --windowed ^
  --name "Compressor de Vídeos" ^
  --icon=icon.ico ^
  --uac-admin ^
  main.py
```

### Método 3: Com ofuscação (para distribuição)
```cmd
pyinstaller ^
  --onefile ^
  --windowed ^
  --name "Compressor de Vídeos" ^
  --icon=icon.ico ^
  --strip ^
  --disable-windowed-traceback ^
  main.py
```

### Executar o exe:
```cmd
dist\"Compressor de Vídeos.exe"
```

---

## 🐧 PARA Linux

### Método básico
```bash
cd "/path/to/Comprimir videos"

pyinstaller \
  --onefile \
  --windowed \
  --name "compressor-videos" \
  main.py
```

**Resultado**: `dist/compressor-videos`

### Executar:
```bash
./dist/compressor-videos
# ou
./dist/compressor-videos &  # em background
```

---

## 🎨 Adicionar Ícone (Opcional mas Recomendado)

### macOS - Criar icon.icns
```bash
# Requer arquivo PNG 1024x1024
# Se não tiver, pode usar:
curl https://via.placeholder.com/1024 -o icon.png

# Converter para ICNS (requer Image2ICNS)
# Ou use online: https://icoconvert.com/
```

### Windows - Usar icon.ico
```cmd
# Usar ferramenta online: https://icoconvert.com/
# Carregar PNG 256x256 ou maior
# Baixar .ico resultante
# Colocar em: C:\Caminho\Comprimir videos\icon.ico
```

### Incluir na geração:
```bash
# macOS
pyinstaller --onefile --windowed --icon=icon.icns --name "Compressor de Vídeos" main.py

# Windows
pyinstaller --onefile --windowed --icon=icon.ico --name "Compressor de Vídeos" main.py
```

---

## 📊 Opções Explicadas

| Opção | O quê faz | Quando usar |
|-------|-----------|------------|
| `--onefile` | Cria executável único | Sempre (distribuição mais fácil) |
| `--windowed` | Remove console de fundo | Interface gráfica |
| `--name` | Nome do executável | Sempre |
| `--icon` | Adiciona ícone | Distribuição profissional |
| `--hidden-import` | Importação não-óbvia | Quando módulos não são detectados |
| `--add-data` | Inclui arquivos extras | Dados não-Python |
| `--strip` | Remove símbolos de debug | Reduz tamanho |
| `--uac-admin` | Solicita permissões admin | Se precisa acessar áreas restritas |

---

## 🧹 Limpar Build Anterior

```bash
cd "/Users/gustavo/Comprimir videos"

# Remover diretórios anteriores
rm -rf build dist *.spec

# Ou no Windows:
rmdir /s build
rmdir /s dist
del *.spec
```

---

## 🔍 Verificar Tamanho Final

### macOS:
```bash
du -sh dist/"Compressor de Vídeos.app"
# app -> ~80MB (com Python embedded)

# Só o executável:
ls -lh dist/"Compressor de Vídeos.app/Contents/MacOS/Compressor de Vídeos"
```

### Windows:
```cmd
dir dist
# .exe será ~50-80MB dependendo de opções
```

---

## 📦 Distribuição

### Para um usuário (enviar arquivo)

**macOS:**
```bash
# Criar arquivo comprimido
cd dist
tar -czf "Compressor de Videos.tar.gz" "Compressor de Vídeos.app"

# Enviar arquivo .tar.gz
# Usuário descompacta:
tar -xzf "Compressor de Videos.tar.gz"
open "Compressor de Vídeos.app"
```

**Windows:**
```cmd
# Simplesmente enviar o .exe
# Usuário clica 2x para executar
```

### Para múltiplos usuários (instalador)

**Windows - Criar instalador MSI:**
```cmd
pip install pyinstaller-windows-msi
pyinstaller --onefile --name "Compressor de Vídeos" main.py
# Usar ferramentas como WiX Toolset para MSI
```

**macOS - Criar DMG:**
```bash
# Instalar dmgbuild
pip install dmgbuild

# Criar DMG
dmgbuild -s settings.py "Compressor de Vídeos" dist/CompressorVideos.dmg
```

---

## 🧪 Testar Executável

### Antes de distribuir, teste:

1. **Limpar cache**:
   ```bash
   rm -rf ~/Library/Application\ Support/Compressor\ de\ Vídeos/  # macOS
   ```

2. **Executar a primeira vez**:
   - Verificar mensagem de FFmpeg
   - Testar seleção de arquivo
   - Testar compressão

3. **Verificar problemas**:
   - Abrir console de erros se houver
   - Testar em máquina sem Python instalado

---

## 🐛 Troubleshooting Empacotamento

### Erro: "ModuleNotFoundError: customtkinter"
**Solução**:
```bash
pyinstaller --hidden-import=customtkinter --onefile main.py
```

### Erro: "No module named '_tkinter'"
**Solução** (macOS):
```bash
# Reinstalar Python com suporte a Tkinter
brew reinstall python-tk@3.13
```

### Executável não roda em outro computador
**Verificar**:
- ❌ FFmpeg instalado no alvo
- ❌ Versão do macOS/Windows compatível
- ❌ Dependências de sistema (libssl, etc no Linux)

### Arquivo muito grande (>200MB)
**Reduzir**:
```bash
pyinstaller \
  --onefile \
  --strip \
  --upx \
  --noupx-exclude='libc.so*' \
  main.py
```

---

## 🚀 Script Automatizado (Recomendado)

Crie `build.sh` (macOS/Linux):

```bash
#!/bin/bash

echo "🔧 Limpando build anterior..."
rm -rf build dist *.spec

echo "📦 Construindo executável..."
pyinstaller \
  --onefile \
  --windowed \
  --name "Compressor de Vídeos" \
  --icon=icon.icns \
  main.py

echo "✅ Build concluído!"
echo "📍 Arquivo: dist/Compressor de Vídeos.app"
```

ou `build.bat` (Windows):

```batch
@echo off
echo 🔧 Limpando build anterior...
rmdir /s /q build
rmdir /s /q dist
del *.spec

echo 📦 Construindo executável...
pyinstaller ^
  --onefile ^
  --windowed ^
  --name "Compressor de Vídeos" ^
  --icon=icon.ico ^
  main.py

echo ✅ Build concluído!
echo 📍 Arquivo: dist\Compressor de Vídeos.exe
pause
```

### Usar:
```bash
chmod +x build.sh
./build.sh
```

---

## 📋 Checklist Final

Antes de distribuir:

- [ ] ✅ Testou compressão localmente
- [ ] ✅ Gerou executável sem erros
- [ ] ✅ Testou executável em máquina limpa
- [ ] ✅ Verificou se FFmpeg foi detectado
- [ ] ✅ Testou com vídeo de verdade (não teste pequenininho)
- [ ] ✅ Verificou resolução de ícone/título
- [ ] ✅ Documentou requisitos de FFmpeg
- [ ] ✅ Criou arquivo README de distribuição

---

## 📄 Exemplo de README para Distribuição

Crie `README_DISTRIBUICAO.md`:

```markdown
# Compressor de Vídeos v1.0.0

## Instalação

### Requisitos Prévios
- **FFmpeg** - [Instalar aqui](https://ffmpeg.org/download.html)

### macOS (Homebrew)
```bash
brew install ffmpeg
open "Compressor de Vídeos.app"
```

### Windows
1. Baixe FFmpeg: https://ffmpeg.org/download.html
2. Extraia em `C:\ffmpeg`
3. Adicione ao PATH (Google: "adicionar ao PATH Windows")
4. Clique duplo em `Compressor de Vídeos.exe`

## Uso
1. Selecione vídeo
2. Configure compressão
3. Clique "COMPRIMIR"

## Suporte
- Documentação: Veja `README.md`
- Problemas: Veja `EXECUCAO_RAPIDA.md`
```

---

## ✅ Resumo

**Comando Rápido (macOS):**
```bash
cd "/Users/gustavo/Comprimir videos"
pyinstaller --onefile --windowed --name "Compressor de Vídeos" main.py
# Resultado: dist/Compressor de Vídeos.app
```

**Comando Rápido (Windows):**
```cmd
cd "C:\Caminho\Comprimir videos"
pyinstaller --onefile --windowed --name "Compressor de Vídeos" main.py
REM Resultado: dist\Compressor de Vídeos.exe
```

---

**Última atualização**: Abril 2026  
**Versão PyInstaller testada**: 6.0+
