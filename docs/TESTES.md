# ✅ GUIA RÁPIDO DE TESTE

Use este guia para validar que tudo está funcionando corretamente antes de usar em produção.

---

## 🚀 Teste 1: Verificar Ambiente (1 minuto)

```bash
cd "/Users/gustavo/Comprimir videos"

# Teste Python
/usr/local/bin/python3 --version
# Deve mostrar: Python 3.x.x

# Teste FFmpeg
which ffmpeg
# Deve mostrar: /usr/local/bin/ffmpeg

# Teste módulos
/usr/local/bin/python3 -c "import customtkinter; print('✅ CustomTkinter OK')"
```

**Resultado esperado**: ✅ Tudo verificado

---

## 🎬 Teste 2: Validar Compressão (5 minutos)

```bash
cd "/Users/gustavo/Comprimir videos"

/usr/local/bin/python3 exemplos.py
```

**Resultado esperado**:
```
✅ FFmpeg disponível
✅ FFprobe disponível
✅ Vídeo lido com sucesso
✅ Perfis de compressão disponíveis
✅ Compressão completada
```

---

## 🖥️ Teste 3: Executar Interface Gráfica (até 30 segundos)

```bash
cd "/Users/gustavo/Comprimir videos"
/usr/local/bin/python3 main.py
```

**Verificar**:
- ❌ Janela abrira em <5 segundos
- ❌ Interface mostra "Bem-vindo ao Compressor"
- ❌ Botão "Selecionar Vídeo" está ativo
- ❌ Não há mensagem de erro vermelha

**Se funcionar**: ✅ Interface OK

---

## 📹 Teste 4: Teste de Compressão Real (variável)

### Passo 1: Preparar vídeo de teste
```bash
# Usar um vídeo real de 1-5 minutos
# Exemplos:
# - MP4 do seu computador
# - MOV do seu iPhone
# - MKV do seu PC
# - WebM do navegador
```

### Passo 2: Executar UI
```bash
/usr/local/bin/python3 main.py
```

### Passo 3: Teste completo
1. Clique "Selecionar Vídeo"
2. Escolha seus arquivos de teste
3. Verifique se informações aparecem:
   - ✅ Nome do arquivo
   - ✅ Tamanho (ex: 150 MB)
   - ✅ Duração (ex: 2:30)
   - ✅ Resolução (ex: 1920x1080)
4. Deixe "Balanceado" selecionado
5. Clique "COMPRIMIR VÍDEO"
6. Aguarde 100% (pode levar 5-30 min dependendo do vídeo)
7. Veja resultado:
   - ✅ Percentual de redução (esperado: ~60%)
   - ✅ Arquivo criado em ...comprimido.mp4
   - ✅ Arquivo playável no seu player favorito

**Se tudo funcionar**: ✅ Compressão OK

---

## 🧪 Teste 5: Teste Todos os Perfis (opcional)

```bash
/usr/local/bin/python3 main.py
```

Com um vídeo pequeno (< 30s):
1. Teste "Alta Qualidade" - deve ser rápido
2. Teste "Balanceado" - deve ser rápido
3. Teste "Compressão Forte" - deve ser rápido
4. Teste "Compressão Máxima" - deve ser bem rápido

**Esperado**: Redução progressiva no tamanho: ~35% → ~60% → ~75% → ~85%

---

## 🎯 Teste 6: Teste Funcionalidades (10 minutos)

Via UI, teste:
- ❌ [x] Selecionar diferentes arquivos
- ❌ [x] Mudar perfil de compressão
- ❌ [x] Mudar resolução
- ❌ [x] Remover áudio (checkbox)
- ❌ [x] Mudar pasta de saída
- ❌ [x] Cancelar compressão a meio
- ❌ [x] Abrir pasta resultante

**Esperado**: Tudo funciona sem travamentos

---

## 🏗️ Teste 7: Empacotamento (5 minutos)

```bash
cd "/Users/gustavo/Comprimir videos"

# Limpar build anterior
rm -rf build dist *.spec

# Gerar executável
pyinstaller --onefile --windowed --name "Compressor de Vídeos" main.py

# Verificar
ls -la dist/
```

**Resultado esperado**:
```
dist/
  └── Compressor de Vídeos.app/  (macOS)
      ou
      Compressor de Vídeos.exe   (Windows)
```

---

## 📊 Resultados de Teste Esperados

### Perfis (teste com vídeo 1 hora, 1080p, 60fps típico):

| Perfil | Redução Esperada | Tempo Processamento |
|--------|-----------------|-------------------|
| Alta Qualidade | 30-35% | 1-2h |
| Balanceado | 55-65% | 40-80 min |
| Compressão Forte | 70-80% | 40-80 min |
| Compressão Máxima | 80-90% | 30-60 min |

### Qualidade Visual:
- **Alta Qualidade**: Praticamente imperceptível
- **Balanceado**: Imperceptível (~99% da qualidade)
- **Compressão Forte**: Perceptível se procurar, aceitável para maioria
- **Compressão Máxima**: Visível (use apenas se necessário)

---

## ⚠️ Cenários Problema

### Problema: Interface não abre
**Teste**:
```bash
/usr/local/bin/python3 -c "import customtkinter; print('OK')"
```
**Se falhar**: Reinstale customtkinter
```bash
/usr/local/bin/python3 -m pip install --upgrade customtkinter
```

### Problema: FFmpeg não encontrado
**Teste**:
```bash
which ffmpeg
ffmpeg -version
```
**Se falhar**: Instale FFmpeg
```bash
brew install ffmpeg  # macOS
```

### Problema: Compressão muito lenta
**Causa**: CPU fraca ou vídeo grande
**Solução**: Use Compressão Máxima (preset fast)

### Problema: Arquivo não muda de tamanho
**Causa esperada**: Vídeo muito pequeno (<5 segundos)
**Normal**: Container MP4 pode ocupar mais que redução
**Teste com**: Vídeo > 1 minuto

---

## 🔍 Validação de Qualidade

### Visualmente:
1. Comprima um vídeo com "Balanceado"
2. Abra original e final lado a lado
3. Compare qualidade
4. **Esperado**: Praticamente idênticos

### Técnicamente:
1. Verifique arquivo final em media player
2. Tente em:
   - ❌ QuickTime Player (macOS)
   - ❌ VLC Media Player
   - ❌ Windows Media Player (Windows)
   - ❌ Navegador web
3. **Esperado**: Funciona em todos

---

## ✅ Checklist de Validação Final

Marque cada teste como OK:

- [ ] ✅ Python 3.8+ instalado
- [ ] ✅ FFmpeg instalado e acessível
- [ ] ✅ CustomTkinter instalado
- [ ] ✅ Exemplos executam sem erro
- [ ] ✅ Interface gráfica abre
- [ ] ✅ Consegue selecionar arquivo
- [ ] ✅ Informações do vídeo aparecem
- [ ] ✅ Consegue selecionar pasta de saída
- [ ] ✅ Consegue comprimir vídeo
- [ ] ✅ Arquivo final é criado
- [ ] ✅ Arquivo final é menor
- [ ] ✅ Arquivo final é playável
- [ ] ✅ Todos os perfis funcionam
- [ ] ✅ Cancelamento funciona
- [ ] ✅ Progresso é mostrado
- [ ] ✅ Executável pode ser gerado
- [ ] ✅ Sem avisos ou erros no console

**Se todo o checklist OK**: ✅ **PRONTO PARA USAR**

---

## 🚨 Suporte Rápido

**Problema** → **Solução**:

| Issue | Fix |
|-------|-----|
| Módulo não encontrado | `pip install -r requirements.txt` |
| FFmpeg não encontrado | `brew install ffmpeg` |
| Interface congela | Aguarde ou clique Cancelar |
| Arquivo não cria | Verifique permissões de pasta |
| Qualidade ruim | Use perfil menos agressivo |
| Muito lento | Use perfil mais agressivo |
| Arquivo muito grande | Reduza resolução |

---

**Tempo total de testes**: ~1 hora (primeira vez)  
**Tempo de reteste**: ~5 minutos

Após todos os testes passarem, o programa está **pronto para produção**.

---

**Última atualização**: Abril 2026
