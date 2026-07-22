# Relatorio de Auditoria do Desktop

Data da auditoria: 2026-07-09

Escopo: arquivos Python atuais do projeto desktop em `/Users/gustavo/Comprimir videos`.

Regra de preservacao aplicada: nenhum arquivo Python existente foi alterado, movido, renomeado ou removido nesta etapa.

## 1. Arquivos analisados

| Arquivo | Responsabilidade |
|---|---|
| `main.py` | Ponto de entrada. Cria a janela `CTk`, instancia `VideoCompressorGUI` e inicia o loop grafico. |
| `ui.py` | Interface grafica CustomTkinter, selecao de arquivos, opcoes, progresso, mensagens, threads de processamento e abertura da pasta de saida. |
| `compressor.py` | Logica de processamento por FFmpeg/FFprobe: localizacao dos binarios, leitura de metadados, montagem do comando de compressao, progresso e cancelamento. |
| `utils.py` | Funcoes auxiliares independentes: formatacao, informacoes do sistema, abertura de pasta, estimativa heuristica e validacao simples de FFmpeg. |
| `exemplos.py` | Exemplos programaticos de uso de `VideoCompressor`; nao participa do fluxo grafico principal. |
| `requirements.txt` | Dependencia Python declarada: `customtkinter==5.2.2`. |

## 2. Classes existentes

| Classe | Arquivo | Responsabilidade |
|---|---|---|
| `VideoCompressor` | `compressor.py` | Encapsula FFmpeg/FFprobe, perfis de compressao, leitura de metadados, compressao, progresso e cancelamento. |
| `VideoCompressorGUI` | `ui.py` | Construcao da interface grafica e orquestracao entre UI e `VideoCompressor`. |

## 3. Funcoes e metodos principais

### `main.py`

- `main()`: cria `ctk.CTk()`, instancia `VideoCompressorGUI(root)`, chama `root.mainloop()`. Em excecao, imprime erro e encerra com `sys.exit(1)`.

### `compressor.py`

- `VideoCompressor._find_ffmpeg()`: procura `ffmpeg`/`ffmpeg.exe` via `which` ou `where`; depois tenta caminhos comuns; retorna fallback `ffmpeg`.
- `VideoCompressor._find_ffprobe()`: procura `ffprobe`/`ffprobe.exe` via `which` ou `where`; depois tenta caminhos comuns; retorna fallback `ffprobe`.
- `VideoCompressor.is_ffmpeg_available()`: executa `[ffmpeg_path, "-version"]` com timeout de 5s.
- `VideoCompressor.is_ffprobe_available()`: executa `[ffprobe_path, "-version"]` com timeout de 5s.
- `VideoCompressor.get_video_info(file_path)`: usa FFprobe para ler `width`, `height`, `duration` do primeiro stream de video e `os.path.getsize`.
- `VideoCompressor._calculate_scale_filter(original_info, target_height)`: retorna `scale=-2:altura` quando aplicavel.
- `VideoCompressor._calculate_effective_height(original_info, rotation)`: se rotacao for 90/270, considera a largura original como altura efetiva.
- `VideoCompressor._get_rotation_filter(rotation)`: mapeia 90 para `transpose=1`, 180 para `hflip,vflip`, 270 para `transpose=2`.
- `VideoCompressor.compress_video(...)`: valida entrada/perfil/rotacao, monta comando FFmpeg, executa em `subprocess.Popen`, processa progresso, retorna `(bool, mensagem)`.
- `VideoCompressor._process_output(duration, progress_callback)`: le `stderr` do FFmpeg e extrai `time=HH:MM:SS.ms` para calcular porcentagem.
- `VideoCompressor.cancel_compression()`: termina ou mata o processo em andamento.

Observacao critica: `ui.py` chama `self.compressor.extract_audio_mp3(...)`, mas `compressor.py` atual no disco nao define `extract_audio_mp3`. Portanto a extracao de MP3 esta exposta na UI, mas o backend esta ausente no codigo atual analisado.

### `ui.py`

- `VideoCompressorGUI.__init__`: inicializa estado, janela, tema, UI e validacao de FFmpeg.
- `_setup_ui()`: cria todas as secoes: entrada, opcoes, saida, progresso, botoes e status.
- `_check_ffmpeg()`: mostra erro se `is_ffmpeg_available()` falhar.
- `_prepare_window_for_dialog()`: tenta focar a janela antes de dialogs nativos.
- `_open_file_dialog(title, filetypes)`: abre `filedialog.askopenfilename`.
- `_open_directory_dialog(title)`: abre `filedialog.askdirectory`.
- `_select_input_file()`: define filtros de video e chama `_update_input_info`.
- `_update_input_info()`: chama `get_video_info`, atualiza tamanho, duracao e resolucao.
- `_select_output_folder()`: define `self.output_folder`.
- `_start_compression()`: valida entrada/FFmpeg/pasta, gera caminho `_comprimido.mp4`, confirma sobrescrita e cria thread.
- `_start_audio_extraction()`: valida entrada/FFmpeg/pasta, gera caminho `_audio.mp3`, confirma sobrescrita e cria thread. Depende de metodo ausente em `compressor.py`.
- `_compression_worker(output_file)`: le opcoes da UI, converte resolucao/rotacao, chama `compress_video`.
- `_audio_extraction_worker(output_file)`: chama `extract_audio_mp3`; falhara em runtime no estado atual por ausencia do metodo.
- `_update_progress(progress)`: agenda atualizacao da UI com `root.after`.
- `_update_progress_ui(progress)`: atualiza barra e label.
- `_show_results(output_file)`: calcula tamanhos, reducao e mostra sucesso da compressao.
- `_show_audio_results(output_file)`: calcula tamanho do MP3 e mostra sucesso da extracao.
- `_open_output_folder(file_path)`: abre pasta via `os.startfile` no Windows ou `open` em POSIX.
- `_cancel_compression()`: confirma e chama `cancel_compression`.
- `_compression_finished()`: reabilita botoes e reseta progresso.
- `_add_status(message)`: escreve no textbox de status.

### `utils.py`

- `format_file_size(bytes_size)`: formata B/KB/MB/GB/TB.
- `format_duration(seconds)`: formata `M:SS` ou `H:MM:SS`.
- `get_system_info()`: retorna dados basicos de `platform`.
- `open_folder_in_explorer(folder_path)`: abre pasta por `open`, `os.startfile` ou `xdg-open`.
- `estimate_output_size(...)`: estimativa heuristica com fatores por perfil.
- `validate_ffmpeg_installation()`: executa `ffmpeg -version` e retorna status/mensagem.

## 4. Dependencias entre modulos

```text
main.py
  -> ui.VideoCompressorGUI
      -> compressor.VideoCompressor
      -> tkinter, customtkinter, pathlib, os, threading, datetime

exemplos.py
  -> compressor.VideoCompressor
  -> utils.format_file_size
  -> utils.format_duration

utils.py
  -> os, platform, subprocess
```

`utils.py` nao e importado pelo fluxo grafico principal.

## 5. Fluxo de inicializacao

1. `python main.py`.
2. `main.py` adiciona o diretorio atual ao `sys.path`.
3. Importa `VideoCompressorGUI`.
4. Cria `root = ctk.CTk()`.
5. Instancia `VideoCompressorGUI(root)`.
6. `VideoCompressorGUI.__init__` instancia `VideoCompressor`.
7. `VideoCompressor.__init__` localiza FFmpeg e FFprobe.
8. UI e montada por `_setup_ui()`.
9. `_check_ffmpeg()` valida disponibilidade do FFmpeg.
10. `root.mainloop()` inicia a aplicacao.

## 6. Como a interface chama o processamento

Compressao:

```text
Botao COMPRIMIR VIDEO
  -> _start_compression()
  -> thread target _compression_worker(output_file)
  -> VideoCompressor.compress_video(...)
```

Extracao MP3:

```text
Botao EXTRAIR MP3
  -> _start_audio_extraction()
  -> thread target _audio_extraction_worker(output_file)
  -> VideoCompressor.extract_audio_mp3(...)
```

Status: fluxo presente na UI, mas metodo ausente em `compressor.py`.

## 7. Progresso

- FFmpeg escreve progresso no `stderr`.
- `_process_output` procura `time=HH:MM:SS.ms`.
- Usa `duration` do FFprobe para calcular `int((current_time / duration) * 100)`.
- Callback recebido por `compress_video` e chamado com porcentagem.
- UI recebe em `_update_progress`, agenda no thread principal com `root.after`, e atualiza `CTkProgressBar`.

Limite conhecido: se `progress_callback` for `None` ou `duration <= 0`, `_process_output` retorna sem consumir `stderr`. Para videos que produzam muita saida em `stderr`, isso pode bloquear o processo por pipe cheio. No fluxo grafico ha callback.

## 8. Tratamento de erros

- Arquivo inexistente: `compress_video` retorna `False, "Arquivo nao encontrado..."`.
- Perfil invalido: retorna erro.
- Rotacao invalida: retorna erro.
- Falha ao ler metadados: retorna erro.
- FFmpeg nao encontrado: UI mostra `messagebox.showerror`.
- Pasta de saida invalida: UI mostra erro.
- Arquivo de saida existente: UI pede confirmacao.
- Excecoes em worker: status + `messagebox.showerror`.
- FFmpeg com codigo diferente de zero: retorna os primeiros 200 caracteres de `stderr`.
- Erros em progresso sao ignorados silenciosamente.

## 9. Caminhos de arquivos

- Entrada: selecionada por `filedialog.askopenfilename`.
- Pasta de saida: selecionada por `filedialog.askdirectory`.
- Se nenhuma pasta de saida for selecionada: usa `Path(self.input_file).parent`.
- Compressao: `stem + "_comprimido.mp4"`.
- Extracao MP3 na UI: `stem + "_audio.mp3"`, mas processamento nao confirmado por backend ausente.
- Original: nao e removido nem sobrescrito. A saida e novo arquivo; pode sobrescrever apenas se o usuario confirmar quando o nome de saida ja existir.

## 10. Localizacao de FFmpeg e FFprobe

Windows:

- Procura `ffmpeg.exe`, `ffmpeg` com `where`.
- Procura `ffprobe.exe`, `ffprobe` com `where`.
- Caminho comum: `C:\ffmpeg\bin\ffmpeg.exe` e `C:\ffmpeg\bin\ffprobe.exe`.

Linux/macOS:

- Procura `ffmpeg` e `ffprobe` com `which`.
- Caminhos comuns: `/usr/bin`, `/usr/local/bin`, `/opt/homebrew/bin`.

Fallback:

- Retorna `"ffmpeg"` ou `"ffprobe"` para deixar o sistema tentar resolver via PATH.

## 11. Executavel empacotado

Nao foi encontrado no codigo atual nenhum tratamento para `sys.frozen`, `_MEIPASS`, PyInstaller runtime path ou empacotamento. Portanto identificacao de executavel empacotado: nao confirmada.

## 12. Especificidades Windows, macOS e Linux

- Localizacao de binarios usa `os.name == "nt"` para `where`; caso contrario `which`.
- Abertura de pasta na UI: Windows usa `os.startfile`; POSIX usa `os.system('open "folder"')`. Observacao: `open` e comando macOS; em Linux esse caminho provavelmente falha.
- `utils.open_folder_in_explorer` tem tratamento mais completo: Darwin `open`, Windows `os.startfile`, Linux `xdg-open`, mas nao e usado pela UI.
- Dialogs nativos usam `tkinter.filedialog`, com tratamento de foco comentado como solucao para macOS.

## 13. Funcionalidades encontradas

| Funcionalidade | Estado no codigo atual |
|---|---|
| Selecionar video | Implementada em `ui.py`. |
| Ler tamanho, duracao e resolucao | Implementada via FFprobe em `compressor.py`. |
| Comprimir video | Implementada em `compressor.py`. |
| Perfis de compressao | Implementados em `COMPRESSION_PROFILES`. |
| Alterar resolucao | Implementada via filtro `scale=-2:altura`. |
| Rotacionar video | UI e backend implementados. |
| Remover audio | Implementada com `-an`. |
| Extrair audio MP3 | UI implementada; backend ausente no `compressor.py` atual. |
| Selecionar pasta de saida | Implementada em `ui.py`. |
| Gerar caminho automatico de saida | Implementado em `ui.py`. |
| Progresso | Implementado para compressao com callback. |
| Cancelamento | Implementado via `terminate`/`kill` do processo. |
| Abrir pasta de saida | Implementado com limitacao Linux. |
| Preservar original | Implementado por gerar arquivo separado. |

## 14. Comandos FFmpeg/FFprobe identificados

### Validacao FFmpeg

```bash
ffmpeg -version
```

### Validacao FFprobe

```bash
ffprobe -version
```

### Metadados de video

```bash
ffprobe -v error -select_streams v:0 -show_entries stream=width,height,duration -of json INPUT
```

### Compressao base

```bash
ffmpeg -i INPUT [-vf FILTROS] -c:v libx264 -crf CRF -preset PRESET [-an | -c:a aac -b:a 128k] -movflags +faststart -y OUTPUT.mp4
```

Filtros possiveis:

- Resolucao: `scale=-2:1080`, `scale=-2:720`, `scale=-2:480`.
- Rotacao 90 direita: `transpose=1`.
- Rotacao 90 esquerda: `transpose=2`.
- Rotacao 180: `hflip,vflip`.
- Combinacao: filtros unidos por virgula, rotacao antes de escala.

### Extracao MP3

Comando nao confirmado no backend atual. A UI espera um arquivo `_audio.mp3`, mas `compressor.py` nao contem o metodo que monta o FFmpeg.

## 15. Perfis atuais

| Nome | CRF | Preset | Codec video | Audio quando mantido | Observacao |
|---|---:|---|---|---|---|
| Alta Qualidade | 18 | `slow` | `libx264` | `aac` 128k | Menos compressao, maxima fidelidade visual. |
| Balanceado | 23 | `medium` | `libx264` | `aac` 128k | Boa reducao com boa qualidade visual. |
| Compressao Forte | 28 | `medium` | `libx264` | `aac` 128k | Foco em reducao agressiva. |
| Compressao Maxima | 32 | `fast` | `libx264` | `aac` 128k | Maxima reducao; verificar qualidade. |

FPS: nao alterado no codigo.

Resolucao: nao faz parte do perfil; e opcao separada da UI (`Original`, `1080p`, `720p`, `480p`).

Parametros extras globais: `-movflags +faststart`, `-y`.

Estimativas de impacto: o codigo produtivo nao define percentuais. `utils.estimate_output_size` e `exemplos.py` usam fatores heuristicas: Alta Qualidade 0.65, Balanceado 0.40, Compressao Forte 0.25, Compressao Maxima 0.15. Esses fatores nao controlam a compressao real.

## 16. Lacunas e comportamentos ambiguos

1. `ui.py` chama `extract_audio_mp3`, mas `compressor.py` nao define esse metodo. Extraido como lacuna critica.
2. `ui.py` importa `tkinter as tk`, mas nao usa diretamente. Nao alterar nesta etapa.
3. `compressor.py` importa `threading` e `Path`, mas nao usa diretamente. Nao alterar nesta etapa.
4. `is_ffprobe_available()` existe, mas `_check_ffmpeg()` nao valida FFprobe.
5. Linux: `_open_output_folder` usa `open`, comando tipico de macOS. `utils.py` tem alternativa `xdg-open`, mas nao e usada.
6. Duracao via `stream=duration` pode estar ausente em alguns arquivos; nao ha fallback para `format=duration`.
7. Se `progress_callback` for ausente, `_process_output` retorna sem consumir `stderr`; risco de travamento em uso programatico.
8. Nao ha verificacao previa de espaco em disco.
9. Nao ha deteccao de arquivo de entrada igual ao output alem do nome automatico.
10. Nao ha tratamento especifico de videos sem audio quando `remove_audio=False`; FFmpeg pode falhar se nao houver stream de audio e `-c:a aac` for aplicado, comportamento nao confirmado.
11. Nao ha identificacao de app empacotado.

## 17. Conclusao da auditoria

O desktop possui fluxo funcional de compressao, resolucao, rotacao, remocao de audio, progresso, cancelamento e preservacao do original. A extracao de audio aparece na UI, mas esta incompleta no backend atual analisado.

A evolucao mobile deve partir de um contrato funcional independente e nao tentar reaproveitar a UI Python. Para Android, o foco inicial deve ser leitura de metadados, compressao MP4 e preservacao do original usando APIs nativas sempre que possivel. FFmpeg mobile deve ser tratado como alternativa ou prova de conceito, nao como dependencia assumida nesta Fase 0.
