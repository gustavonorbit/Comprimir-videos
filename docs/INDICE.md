# 📚 MAPA DE DOCUMENTAÇÃO

Use este arquivo como guia para encontrar o que você procura.

---

## 🎯 COMECE AQUI

### 📖 Seu primeiro documento
👉 **[RESUMO.md](RESUMO.md)** - Visão geral 5 minutos (o que foi criado, como funciona)

### 🚀 Executar agora
```bash
/usr/local/bin/python3 main.py
```

### ✅ Validar que funciona
👉 **[TESTES.md](TESTES.md)** - 7 testes rápidos (~1 hora)

---

## 📖 DOCUMENTAÇÃO POR TÓPICO

### 🤔 "Quero entender o programa"
1. [RESUMO.md](RESUMO.md) - Visão geral (5 min)
2. [README.md](README.md) - Documentação completa (10 min)
3. [exemplos.py](exemplos.py) - Exemplos de código (5 min)

### 🚀 "Quero começar a usar agora"
1. [EXECUCAO_RAPIDA.md](EXECUCAO_RAPIDA.md) - Terminal em 1 minuto
2. [main.py](main.py) - Execute isto

### 🔬 "Quero conhecer a técnica"
1. [TECNICA_DETALHADA.md](TECNICA_DETALHADA.md) - Explicação científica (H.264, CRF, etc)
2. [compressor.py](compressor.py) - Código fonte da compressão

### 📦 "Quero criar um executável"
1. **Windows**: [EMPACOTAMENTO.md](EMPACOTAMENTO.md) → seção Windows
2. **macOS**: [EMPACOTAMENTO.md](EMPACOTAMENTO.md) → seção macOS
3. **Linux**: [EMPACOTAMENTO.md](EMPACOTAMENTO.md) → seção Linux

### 🐛 "Algo não funciona"
1. [EXECUCAO_RAPIDA.md](EXECUCAO_RAPIDA.md) → Troubleshooting Rápido
2. [README.md](README.md) → Solução de Problemas
3. [TESTES.md](TESTES.md) → Cenários Problema

### 💻 "Quero usar em meu código"
1. [exemplos.py](exemplos.py) - 7 exemplos de uso
2. [compressor.py](compressor.py) - Documentação da API
3. [utils.py](utils.py) - Funções auxiliares

---

## 📄 LISTA DE ARQUIVOS

### 🐍 Código Python

| Arquivo | Tamanho | Propósito |
|---------|---------|-----------|
| [main.py](main.py) | 716 B | Ponto de entrada (execute isto) |
| [ui.py](ui.py) | 21 KB | Interface gráfica (CustomTkinter) |
| [compressor.py](compressor.py) | 12 KB | Compressão com FFmpeg |
| [utils.py](utils.py) | 4.3 KB | Funções auxiliares |
| [exemplos.py](exemplos.py) | 9.7 KB | 7 exemplos práticos |

### 📚 Documentação

| Arquivo | Tamanho | Público-alvo |
|---------|---------|-------------|
| [RESUMO.md](RESUMO.md) | 12 KB | Todos |
| [README.md](README.md) | 6.9 KB | Usuários do programa |
| [EXECUCAO_RAPIDA.md](EXECUCAO_RAPIDA.md) | 3.2 KB | Uso rápido |
| [TECNICA_DETALHADA.md](TECNICA_DETALHADA.md) | 9.1 KB | Técnicos/curiosos |
| [EMPACOTAMENTO.md](EMPACOTAMENTO.md) | 8.5 KB | Desenvolvedores |
| [TESTES.md](TESTES.md) | 6.4 KB | QA/Validação |

### 📋 Configuração

| Arquivo | Conteúdo |
|---------|----------|
| [requirements.txt](requirements.txt) | customtkinter==5.2.2 |

---

## 🗺️ ROTEIROS RECOMENDADOS

### Roteiro 1: "Quero usar agora" (5 minutos)
```
1. Execute:  /usr/local/bin/python3 main.py
2. Selecione vídeo
3. Clique COMPRIMIR
4. Aproveite o MP4 comprimido
```

### Roteiro 2: "Quero entender antes" (20 minutos)
```
1. Leia: RESUMO.md
2. Leia: TECNICA_DETALHADA.md (perfis de compressão)
3. Execute: exemplos.py
4. Use: main.py
```

### Roteiro 3: "Vou distribuir" (30 minutos)
```
1. Leia: RESUMO.md
2. Execute testes: TESTES.md
3. Gerar exec: EMPACOTAMENTO.md
4. Distribuir a pasta dist/
```

### Roteiro 4: "Vou integrar em meu projeto" (45 minutos)
```
1. Leia: exemplos.py
2. Leia: compressor.py
3. Copie compressor.py para seu projeto
4. Importe e use:
   from compressor import VideoCompressor
```

---

## 🔍 BUSCA RÁPIDA

### Palavras-chave

**H.264**: [TECNICA_DETALHADA.md](TECNICA_DETALHADA.md#2-parâmetros-h264-explicados)  
**CRF**: [TECNICA_DETALHADA.md](TECNICA_DETALHADA.md#crfconstant-rate-factor)  
**Preset**: [TECNICA_DETALHADA.md](TECNICA_DETALHADA.md#preset-de-codificação)  
**FFmpeg não encontrado**: [EXECUCAO_RAPIDA.md](EXECUCAO_RAPIDA.md#p-ffmpeg-não-encontrado)  
**Como comprimir**: [README.md](README.md#-como-usar)  
**Criar executável**: [EMPACOTAMENTO.md](EMPACOTAMENTO.md)  
**Comparar perfis**: [TECNICA_DETALHADA.md](TECNICA_DETALHADA.md#7-estratégia-recomendada)  
**Exemplos código**: [exemplos.py](exemplos.py)  
**Interface congela**: [EXECUCAO_RAPIDA.md](EXECUCAO_RAPIDA.md#p-a-ui-não-abre)  

---

## 📊 TAMANHO TIPO POR USO

### Uso casual (10 min/dia)
- Leia: **README.md**
- Ignore: TECNICA_DETALHADA.md, EMPACOTAMENTO.md
- Execute: main.py

### Uso profissional
- Leia: Tudo
- Execute testes
- Gere executável
- Distribua

### Desenvolvimento
- Estude: compressor.py, ui.py
- Execute: exemplos.py  
- Integrate: Copie compressor.py

---

## ✅ CHECKLIST DE LEITURA

Marque conforme você lê (opcional):

- [ ] RESUMO.md - Visão geral
- [ ] README.md - Como usar
- [ ] EXECUCAO_RAPIDA.md - Teste rápido (opcional)
- [ ] TECNICA_DETALHADA.md - Entender a compressão (opcional)
- [ ] EMPACOTAMENTO.md - Se criar executável (opcional)
- [ ] TESTES.md - Validar sistema (opcional)
- [ ] exemplos.py - Ver exemplos (opcional)

---

## 🎯 PERGUNTAS FREQUENTES (Rápidas)

**P: Por onde começo?**  
R: Execute `python3 main.py`

**P: Qual perfil usar?**  
R: Comece com "Balanceado" (padrão)

**P: O arquivo final é menor?**  
R: Sim, ~60% do tamanho original com Balanceado

**P: FFmpeg está instalado?**  
R: Execute `/usr/local/bin/python3 exemplos.py` para verificar

**P: Preciso conhecer Python?**  
R: NÃO, simples cliques na interface

**P: Posso ver o código fonte?**  
R: SIM, abra qualquer arquivo .py com editor de texto

**P: Como criar executável?**  
R: [EMPACOTAMENTO.md](EMPACOTAMENTO.md) → seu OS

---

## 🌍 IDIOMA

Todos os documentos estão em **Português (Brasil)**.

Comments no código também em português para sua facilidade.

---

## 📱 TEMPO DE LEITURA

| Documento | Tempo |
|-----------|-------|
| RESUMO.md | 5 min |
| README.md | 10 min |
| EXECUCAO_RAPIDA.md | 3 min |
| TECNICA_DETALHADA.md | 15 min |
| EMPACOTAMENTO.md | 10 min |
| TESTES.md | 5 min |
| **TOTAL (todos)** | **~1 hora** |

---

## 🚀 PRÓXIMO PASSO

🎬 **Clique aqui**: Abra o terminal e execute:
```bash
/usr/local/bin/python3 /Users/gustavo/Comprimir\ videos/main.py
```

O programa abrirá em <5 segundos. É só isso! 😊

---

**Última atualização**: 22 de Abril de 2026  
**Versão**: 1.0.0  
**Status**: ✅ Completo
