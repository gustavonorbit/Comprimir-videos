# Análise: Robustez e Design — Compressor de Vídeos (Desktop)

Baseado na leitura de `ui.py`, `compressor.py`, `main.py`, `utils.py` e do relatório de auditoria já existente (`RELATORIO_AUDITORIA_DESKTOP.md`).

## 1. Por que o dropdown de nível de compressão "não aparece"

Duas causas prováveis, e que provavelmente estão somadas:

**a) Linha de opções sobrecarregada.** Em `ui.py` (linhas 161–224), os três dropdowns (Qualidade, Resolução, Rotação) e o checkbox "Remover áudio" estão todos empacotados lado a lado (`side=LEFT`) na mesma linha, dentro de `opt_container`. Dois deles usam `fill=X, expand=True` competindo por espaço com um terceiro de largura fixa (130px) e um checkbox. Em janelas menores que 900px, ou em telas de resolução mais baixa, o combo "Qualidade" — que tem os textos mais longos ("Compressão Máxima", "Compressão Forte") — é o mais espremido e pode renderizar com largura insuficiente para mostrar as opções.

**b) Bug conhecido do CustomTkinter no macOS.** O projeto usa `customtkinter==5.2.2` (`requirements.txt`). Nessa versão, é um problema documentado que o menu suspenso de `CTkComboBox`/`CTkOptionMenu` pode renderizar com fundo transparente/invisível em macOS com Tcl/Tk 8.6.12–8.6.13 (o Tk que vem com o Python do site oficial ou do Homebrew em várias versões recentes). O menu tecnicamente abre e é clicável, mas o texto não aparece — o que bate exatamente com o sintoma relatado.

**Como confirmar rapidamente:** rodar `python3 -c "import tkinter; print(tkinter.TkVersion)"` no ambiente onde o app roda. Se dor 8.6, o problema é esse. Correção mais direta: instalar Python via `brew install python-tk@3.11` (ou versão equivalente) com Tcl/Tk 8.6.14+, ou trocar `CTkComboBox` por `CTkOptionMenu` com estilo próprio, que sofre menos com esse bug. De qualquer forma, a linha sobrecarregada (item a) deve ser corrigida independentemente — é bug de layout real, não só suspeita.

## 2. Bug crítico de robustez: extração de MP3 quebrada

`ui.py` chama `self.compressor.extract_audio_mp3(...)` (linhas 654 e mais), mas esse método **não existe** em `compressor.py`. Qualquer clique em "EXTRAIR MP3" lança `AttributeError`, capturado pelo `try/except` genérico e mostrado como "Erro inesperado" — uma funcionalidade anunciada no README que está quebrada em produção. É o item de maior prioridade antes de qualquer trabalho visual.

## 3. Outras lacunas de robustez (da auditoria + revisão própria)

- **Abrir pasta no Linux quebrado**: `_open_output_folder` usa `os.system('open ...')`, comando exclusivo do macOS. Em Linux, precisa de `xdg-open` (já existe implementação correta em `utils.py`, mas não é usada pela UI).
- **Sem verificação de espaço em disco** antes de iniciar a compressão — pode falhar no meio do processo em vídeos grandes.
- **Sem fallback de duração**: `get_video_info` lê só `stream=duration`; alguns contêineres (ex.: alguns `.mkv`/`.avi`) não expõem duração no stream de vídeo, só no `format`. Isso derruba silenciosamente a leitura de metadados e trava a barra de progresso (progress_callback não é chamado se `duration <= 0`).
- **Vídeo sem faixa de áudio**: se `remove_audio=False` e o vídeo não tiver áudio, o FFmpeg pode falhar ao aplicar `-c:a aac`, sem tratamento prévio.
- **UI trava durante seleção do arquivo**: metadados são lidos de forma síncrona em `_update_input_info` (chamada direto na thread principal). Em arquivos grandes/rede lenta, a janela congela por alguns segundos ao selecionar o vídeo.
- **Sem cache/estado entre sessões**: última pasta usada, último perfil escolhido, etc. não são lembrados — a cada abertura o usuário reconfigura tudo.
- **Sem validação de formato antes de comprimir**: só se descobre que o arquivo é inválido quando o FFprobe falha, sem preview nem checagem antecipada.
- **`is_ffprobe_available()` existe mas nunca é chamado** em `_check_ffmpeg()` — só valida o `ffmpeg`, não o `ffprobe`, mesmo sendo indispensável para ler metadados.

Prioridade sugerida: corrigir `extract_audio_mp3`, abrir pasta multiplataforma, e fallback de duração são bloqueadores reais de uso — o resto é hardening.

## 4. Redesign visual (mais futurista/envolvente)

O visual atual é funcional, mas é "flat dark generic" — fundo `#1a1a1a`, cards `#262626`, um único azul de destaque (`#0078d4`). Para um efeito mais moderno sem reescrever tudo:

- **Paleta com gradiente de acento**: substituir o azul plano por um gradiente sutil (ex. roxo→ciano ou azul→verde-água) nos elementos de ação principais (botão Comprimir, barra de progresso). CustomTkinter não faz gradiente nativo em botões, mas dá para simular com `CTkImage` gerado via Pillow, ou usar duas cores complementares nos dois botões principais para criar contraste visual.
- **Cards com profundidade**: aumentar levemente o `corner_radius`, usar bordas finas semitransparentes (`border_width=1`, cor `#3a3a3a`) para dar sensação de camadas/glassmorphism leve, em vez de blocos sólidos idênticos.
- **Hierarquia tipográfica mais clara**: hoje quase tudo usa 10–12px. Aumentar o contraste de tamanho entre título de seção, valor e legenda ajuda a leitura rápida (ex. tamanho do arquivo em destaque grande, "MB" pequeno ao lado).
- **Estado vazio mais convidativo**: a área de seleção de arquivo hoje é só um botão. Uma zona de **drag-and-drop** com borda tracejada, ícone central e texto "Solte o vídeo aqui ou clique para selecionar" comunica modernidade e já economiza um clique.
- **Feedback de progresso mais rico**: mostrar velocidade de processamento, tempo estimado restante e um contador do tamanho final estimado em tempo real (já é tecnicamente possível parseando mais campos do stderr do FFmpeg, como `bitrate=` e `speed=`).
- **Micro-animações**: CustomTkinter permite transições simples (fade ao trocar de estado, pulso na barra de progresso) que dão sensação de "vivo" sem framework externo.

## 5. Fluxo extremamente rápido (a premissa do produto)

Pontos que hoje custam cliques/tempo desnecessários:

1. **Drag-and-drop do vídeo** direto na janela — elimina o passo "Selecionar Vídeo" para quem já tem o arquivo à mão (Finder/Explorer aberto).
2. **Perfil como botões de um clique**, não dropdown — para 4 opções fixas, uma barra de 4 chips ("Alta", "Balanceado", "Forte", "Máxima") é mais rápida de usar que abrir e escolher em um combo, e resolve de vez o bug de renderização do dropdown.
3. **Pasta de saída com padrão inteligente e memória**: já usa a pasta do vídeo por padrão (bom); adicionar "lembrar última pasta usada" evita repetir escolha a cada sessão.
4. **Comprimir com um clique após soltar o arquivo**: opcional um modo "auto" — solta o vídeo, mostra perfil padrão pré-selecionado, e o usuário só confirma. Reduz o fluxo de ~5 cliques para 2.
5. **Preview de tamanho estimado antes de rodar**: hoje o usuário só sabe o resultado depois de esperar o processamento inteiro. Mostrar uma estimativa (usando a heurística que já existe em `utils.estimate_output_size`, hoje não usada pela UI) antes de começar dá confiança para decidir o perfil sem tentativa-e-erro.
6. **Atalhos de teclado**: Cmd/Ctrl+O para abrir arquivo, Cmd/Ctrl+Enter para comprimir, Esc para cancelar — comum em ferramentas rápidas e hoje ausente.
7. **Fila de múltiplos arquivos**: se o uso real for comprimir vários vídeos, hoje é um de cada vez, com o usuário tendo que repetir o fluxo inteiro. Uma fila com processamento sequencial automático é o maior ganho de tempo percebido se esse for um caso de uso comum.

## 6. Plano de ação priorizado

**Bloqueadores (fazer primeiro):**
1. Implementar `extract_audio_mp3` em `compressor.py` (ou remover o botão até existir).
2. Corrigir layout da linha de opções (quebrar em duas linhas ou usar grid em vez de pack lado a lado) — resolve o dropdown espremido.
3. Confirmar/corrigir o bug do Tcl/Tk no macOS (checar versão, migrar para `CTkOptionMenu` estilizado se necessário).
4. Corrigir abertura de pasta no Linux (usar a função já existente em `utils.py`).

**Robustez (segunda onda):**
5. Fallback de duração via `format=duration` no FFprobe.
6. Checagem de espaço em disco e de faixa de áudio antes de comprimir.
7. Mover leitura de metadados para thread separada (não travar UI ao selecionar arquivo).
8. Validar `ffprobe` em `_check_ffmpeg()`.

**Design e velocidade de fluxo (terceira onda):**
9. Zona de drag-and-drop + chips de perfil em vez de dropdown.
10. Estimativa de tamanho final antes de processar (reaproveitar `estimate_output_size`).
11. Memória de preferências (última pasta, último perfil).
12. Atalhos de teclado e, se fizer sentido para o uso real, fila de múltiplos arquivos.

Posso implementar qualquer um desses itens diretamente no código — é só apontar por onde começar (sugestão: itens 1 a 4, que resolvem os bugs visíveis hoje).
