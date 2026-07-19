# 🎬 Compressor de Vídeos

Um programa desktop simples, rápido e profissional para compressão de vídeos com interface gráfica amigável. Foca em máxima compatibilidade, alta redução de tamanho e preservação razoável da qualidade visual.

## ✨ Características

- **Interface moderna**: Construída com CustomTkinter para visual profissional
- **Compressão eficiente**: H.264 + AAC com CRF ajustável
- **Múltiplos formatos de entrada**: Aceita praticamente qualquer vídeo suportado pelo FFmpeg
- **Saída universal em MP4**: Máxima compatibilidade
- **4 perfis de compressão**: Da alta qualidade à máxima compressão
- **Controle de resolução**: Original, 1080p, 720p ou 480p
- **Rotação manual**: Vire vídeos em 90° para direita, 90° para esquerda ou 180°
- **Opção de remover áudio**: Para compressão ainda maior
- **Extração de áudio em MP3**: Gera um arquivo `.mp3` a partir do vídeo importado
- **Processamento não bloqueante**: Interface responsiva com barra de progresso real
- **Pronto para empacotamento**: Estrutura preparada para PyInstaller

## 📋 Requisitos

### Sistema
- Python 3.8+
- FFmpeg instalado e acessível via PATH

### Dependências Python (automáticas)
- CustomTkinter 5.2.2 - Interface gráfica moderna

## 🚀 Instalação Rápida

### 1. Clonar/Baixar o projeto
```bash
git clone <url-do-repositorio>
cd "Comprimir videos"
```

### 2. Criar ambiente virtual (recomendado)

**macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Instalar dependências
```bash
pip install -r requirements.txt
```

### 4. Instalar FFmpeg

**macOS (Homebrew):**
```bash
brew install ffmpeg
```

**Windows (Chocolatey):**
```bash
choco install ffmpeg
```

**Windows (Manual):**
1. Baixe de: https://ffmpeg.org/download.html
2. Extraia em uma pasta (ex: C:\ffmpeg)
3. Adicione ao PATH do Windows

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install ffmpeg
```

**Linux (Fedora/RHEL):**
```bash
sudo dnf install ffmpeg
```

### 5. Executar a aplicação
```bash
python main.py
```

## 📖 Como Usar

1. **Selecione um Vídeo**
   - Clique em "Selecionar Vídeo"
   - O programa exibe: tamanho, duração e resolução

2. **Configure a Compressão**
   - **Qualidade**: Escolha entre Alta Qualidade, Balanceado, Compressão Forte ou Máxima
   - **Resolução**: Mantenha original ou reduza para 1080p, 720p ou 480p
   - **Rotação**: Use quando o vídeo estiver deitado ou invertido
   - **Áudio**: Opcionalmente remova para compressão ainda maior

3. **Defina Pasta de Saída** (opcional)
   - Por padrão, salva na mesma pasta do vídeo original
   - Use "Selecionar Pasta de Saída" para escolher outro local

4. **Clique em "COMPRIMIR VÍDEO"**
   - Acompanhe o progresso em tempo real
   - Use "Cancelar" se precisar interromper

   **Ou clique em "EXTRAIR MP3"**
   - O programa salva o áudio do vídeo em um arquivo `.mp3`
   - Se o vídeo não tiver áudio, a ferramenta avisa antes de processar

5. **Veja os Resultados**
   - Na compressão: tamanho original, final e percentual de redução
   - Na extração: tamanho final do MP3
   - Abra a pasta contendo o arquivo final

## ⚙️ Perfis de Compressão Explicados

### Alta Qualidade
- **CRF**: 18 (mais baixo = melhor qualidade)
- **Preset**: slow (mais tempo, mas mais eficiente)
- **Uso**: Quando qualidade visual é crítica
- **Redução típica**: 30-35%

### Balanceado ⭐ (Recomendado)
- **CRF**: 23 (padrão FFmpeg)
- **Preset**: medium
- **Uso**: Melhor custo-benefício para maioria dos casos
- **Redução típica**: 60%

### Compressão Forte
- **CRF**: 28 (qualidade menor mas ainda aceitável)
- **Preset**: medium
- **Uso**: Quando tamanho é prioridade
- **Redução típica**: 75%

### Compressão Máxima
- **CRF**: 32 (máxima compressão)
- **Preset**: fast (mais rápido, menos eficiente)
- **Uso**: Apenas para distribuição com requisitos extremos
- **Redução típica**: 85%
- **Aviso**: Qualidade visual pode ser notoriamente inferior

## 🎯 Estratégia de Compressão H.264

O programa usa o codec H.264 (MPEG-4 AVC), que é:
- **Amplamente compatível**: Reproduz em praticamente todos os dispositivos
- **Eficiente**: Excelente relação qualidade/tamanho
- **Estável**: Codec maduro e confiável

### Configurações técnicas:
- **Codec de vídeo**: libx264 (FFmpeg H.264)
- **Taxa de bits**: Controlada pelo CRF (Constant Rate Factor)
- **Codec de áudio**: AAC @ 128kbps (padrão)
- **Container**: MP4 (máxima compatibilidade)
- **Otimização**: Fast start para streaming progressivo
- **Rotação**: Filtros FFmpeg `transpose`, `hflip` e `vflip`
- **Extração MP3**: libmp3lame @ 192kbps

## 📦 Criar Executável com PyInstaller

### 1. Instalar PyInstaller
```bash
pip install pyinstaller
```

### 2. Gerar executável (para seu sistema operacional)

**macOS:**
```bash
pyinstaller --onefile --windowed \
  --name "Compressor de Vídeos" \
  --icon=icon.icns \
  main.py
```

**Windows:**
```bash
pyinstaller --onefile --windowed ^
  --name "Compressor de Vídeos" ^
  --icon=icon.ico ^
  main.py
```

**Linux:**
```bash
pyinstaller --onefile --windowed \
  --name "Compressor de Vídeos" \
  main.py
```

### 3. Localize o executável
- **Arquivo gerado em**: `dist/` ou `dist/Compressor de Vídeos.exe`

### 4. Distribuir

O executável é **portável** e não requer instalação, mas:
- **FFmpeg ainda é necessário** instalado no sistema onde usar

## 🔧 Estrutura do Projeto

```
Comprimir videos/
├── main.py              # Ponto de entrada
├── ui.py                # Interface gráfica (CustomTkinter)
├── compressor.py        # Lógica de compressão (FFmpeg)
├── utils.py             # Funções auxiliares
├── requirements.txt     # Dependências Python
└── README.md           # Este arquivo
```

## 🐛 Solução de Problemas

### FFmpeg não encontrado
**Solução**: Instale FFmpeg e adicione ao PATH do sistema, ou especifique o caminho completo no código.

### Interface não aparece/congela
**Solução**: O FFmpeg pode estar rodando. Aguarde ou clique "Cancelar".

### Arquivo final de qualidade ruim
**Solução**: Use um perfil menos agressivo (ex: Balanceado em vez de Máxima).

### Erro "FFmpeg retornou código não-zero"
**Solução**: Verifique se o arquivo de entrada é um vídeo válido.

### Arquivo não é criado
**Solução**: Verifique se a pasta de saída tem permissão de escrita.

## 💡 Dicas de Uso

1. **Teste antes**: Sempre teste com arquivo pequeno antes de processar lotes
2. **Perfil Balanceado**: Na maioria dos casos, oferece o melhor custo-benefício
3. **Reduza resolução**: Se gerar arquivo muito grande, reduza para 720p
4. **Remova áudio se não precisar**: Economiza 10-15% adicionalmente
5. **Use preset slow em Alta Qualidade**: Gera arquivos menores e melhores

## 📝 Notas Técnicas

- **CRF**: Constant Rate Factor (0-51, default 23). Menor = melhor qualidade
- **Preset**: Afeta velocidade de codificação vs eficiência (ultrafast a veryslow)
- **H.264**: Codec de vídeo mais compatível e eficiente disponível
- **AAC**: Codec de áudio moderno, compatível com praticamente tudo

## 🔒 Privacidade

Todos os arquivos são processados **localmente**. Nenhuma informação é enviada para servidores.

## 📄 Licença

Este projeto é fornecido como está para uso pessoal e comercial.

## 👤 Desenvolvido com ❤️

Desenvolvido para oferecer uma solução simples, rápida e profissional para compressão de vídeos.

---

**Última atualização**: Abril 2026

**Versão**: 1.0.0
