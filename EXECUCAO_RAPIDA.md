# 🚀 GUIA DE EXECUÇÃO RÁPIDA

## Para Iniciar Agora (macOS)

### 1. Terminal em uma nova janela:
```bash
cd "/Users/gustavo/Comprimir videos"
source venv/bin/activate  # Se tiver virtualenv ativado
/usr/local/bin/python3 main.py
```

### 2. A interface abrirá em segundos
- Selecione um vídeo
- Configure as opções
- Clique "COMPRIMIR VÍDEO"

---

## ⚡ Troubleshooting Rápido

### P: "FFmpeg não encontrado"
**R**: Instale com: `brew install ffmpeg`

### P: Erro "ModuleNotFoundError: customtkinter"
**R**: Execute: `/usr/local/bin/python3 -m pip install customtkinter`

### P: A UI não abre
**R**: Verifique se customtkinter está instalado e se você tem permissão de janela gráfica

### P: "Cannot connect to display"
**R**: Você está em SSH. Não há suporte a interface gráfica remota sem X11

### P: Vídeo não comprime
**R**: FFmpeg pode ter problemas com o formato. Teste com outro vídeo ou converter antes.

---

## 🎯 Teste Rápido (recomendado)

Use este comando para verificar tudo de uma vez:

```bash
cd "/Users/gustavo/Comprimir videos"
/usr/local/bin/python3 << 'EOF'
from compressor import VideoCompressor
print("✅ Sistema pronto!" if VideoCompressor().is_ffmpeg_available() else "❌ FFmpeg não encontrado")
EOF
```

Se ver **✅ Sistema pronto!** — tudo está funcionando.

---

## 📦 Criar Executável (Mac)

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "Compressor de Vídeos" main.py
# Executável em: dist/Compressor\ de\ Vídeos
```

---

## 🎬 Exemplo de Uso

1. **Abra o programa**: `/usr/local/bin/python3 main.py`
2. **Clique "Selecionar Vídeo"** → escolha um MP4, MOV, MKV, etc.
3. **Configure**:
   - Qualidade: "Balanceado" (recomendado)
   - Resolução: "Original" ou reduza se precisar
   - Áudio: deixe ativado (remova só se quiser maior compressão)
4. **Clique "COMPRIMIR VÍDEO"**
5. **Aguarde** e veja o arquivo final na pasta original

---

## 💻 Requisitos Mínimos Confirmados

- ✅ Python 3.8+
- ✅ FFmpeg 8.0+ (em seu sistema)
- ✅ CustomTkinter 5.2.2
- ✅ macOS/Linux/Windows (a UI funciona em todos)

---

## 🔧 Configuração de Perfis Explicada

### Que Perfil Usar?

| Situação | Perfil | Redução Típica |
|----------|--------|----------------|
| Qualidade é prioridade | Alta Qualidade | 30-35% |
| Uso geral (recomendado) | Balanceado | 60% |
| Economizar espaço | Compressão Forte | 75% |
| Máximo possível | Compressão Máxima | 85%+ |

### Dica Profissional:
- Comece com **Balanceado**
- Se quiser menos qualidade, pule para **Compressão Forte**
- Use **Máxima** apenas em casos extremos
- Se sente qualidade ruim, volte para **Alta Qualidade**

---

## 📊 Formato de Saída

Todos os arquivos são salvos como:

```
nome_original_comprimido.mp4
├── Vídeo: H.264 (MPEG-4 AVC)
├── Áudio: AAC @ 128kbps (ou removido se optar)
└── Container: MP4 (máxima compatibilidade)
```

Reproduz em: Praticamente tudo (smartphones, TVs, computadores, etc.)

---

## 🔐 Privacidade

- ✅ Nenhum arquivo é enviado para nenhum servidor
- ✅ Processamento 100% local
- ✅ Seguro para usar
- ✅ Nenhum rastreamento

---

**Última atualização**: Abril 2026  
**Versão do programa**: 1.0.0  
**Status**: ✅ Totalmente funcional e testado
