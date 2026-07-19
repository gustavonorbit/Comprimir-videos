# Mapeamento Desktop-Mobile

Objetivo: contrato funcional entre o desktop Python atual e o futuro app mobile Android/iOS.

Status: Fase 0, auditoria. Nenhuma implementacao mobile criada.

## Regras globais preservadas

- O arquivo original nunca deve ser alterado.
- Quando o usuario nao escolhe pasta de saida, o desktop salva na mesma pasta do video original.
- A saida de compressao deve ser MP4.
- A interface deve exibir progresso quando a operacao permitir.
- Erros devem ser mostrados de forma amigavel.
- O processamento deve ser assincrono para nao travar a interface.
- Cancelamento deve interromper a operacao em andamento quando possivel.

## Selecao de video

Desktop:
- Implementado em `ui.py`, metodo `_select_input_file`.
- Usa `filedialog.askopenfilename`.
- Filtros: `*.mp4 *.mov *.mkv *.avi *.wmv *.flv *.webm *.m4v *.mpeg *.mpg *.3gp *.ts *.mts *.m2ts`.
- Depois chama `_update_input_info`.

Android:
- Usar seletor de arquivos/midia do Android via Flutter + integracao nativa quando necessario.
- Deve aceitar videos da galeria e arquivos.
- Deve trabalhar com URI/conteudo, copiando para cache quando o motor nativo exigir path.

iOS:
- Usar Photos framework/document picker via Flutter + Swift.
- Deve lidar com permissoes de fotos e arquivos.

Diferencas inevitaveis:
- Mobile usa URIs e permissao granular; desktop usa path direto.

Criterios de aceite:
- Usuario seleciona video valido.
- App mostra nome/tamanho/duracao/resolucao.
- Cancelamento do picker nao gera erro.

Riscos tecnicos:
- Android scoped storage.
- iOS acesso limitado a biblioteca.

Dependencias:
- Android: Photo Picker/Storage Access Framework, `MediaMetadataRetriever`.
- iOS: Photos framework, AVFoundation.

## Leitura de duracao, resolucao e tamanho

Desktop:
- `VideoCompressor.get_video_info`.
- Comando:

```bash
ffprobe -v error -select_streams v:0 -show_entries stream=width,height,duration -of json INPUT
```

- Retorna `width`, `height`, `duration`, `file_size`.

Android:
- Usar `MediaMetadataRetriever` para duracao, largura, altura e metadata.
- Tamanho via `ContentResolver`/arquivo local.

iOS:
- Usar `AVAsset` para duracao e tracks; tamanho via file attributes quando disponivel.

Diferencas inevitaveis:
- Duracao pode vir de container/track de forma diferente.
- URI remota ou cloud pode exigir copia local.

Criterios de aceite:
- Exibir tamanho em MB, duracao e resolucao.
- Arquivo invalido deve gerar mensagem amigavel.

Riscos tecnicos:
- Metadados incompletos.
- Videos corrompidos.

Dependencias:
- Android: `MediaMetadataRetriever`.
- iOS: AVFoundation.

## Compressao de video

Desktop:
- `VideoCompressor.compress_video`.
- Entrada: `input_file`, `output_file`, `profile`, `resolution`, `remove_audio`, `rotation`, `progress_callback`.
- Saida: `(success: bool, message: str)`.
- Comando base:

```bash
ffmpeg -i INPUT [-vf FILTROS] -c:v libx264 -crf CRF -preset PRESET [-an | -c:a aac -b:a 128k] -movflags +faststart -y OUTPUT.mp4
```

- Nome de saida na UI: `{nome}_comprimido.mp4`.
- Se pasta nao selecionada: mesma pasta do original.
- Mensagem de sucesso: `Video comprimido com sucesso!`.

Android:
- MVP deve produzir MP4 preservando original.
- Preferir AndroidX Media3 Transformer/MediaCodec/MediaMuxer para compressao nativa.
- A equivalencia exata de CRF/preset nao e garantida em APIs nativas; deve mapear perfis para parametros de bitrate/qualidade apos prova de conceito.

iOS:
- Futuro equivalente com AVFoundation (`AVAssetExportSession`, `AVAssetReader`, `AVAssetWriter`).
- Equivalencia exata de CRF/preset nao e garantida.

Diferencas inevitaveis:
- Desktop usa `libx264` CRF/preset; mobile nativo tende a usar H.264 hardware com bitrate/profile.
- Resultado final pode diferir em tamanho e qualidade.

Criterios de aceite:
- Saida MP4.
- Original preservado.
- Progresso exibido.
- Resultado salvo corretamente.
- Erro tratado de forma amigavel.
- Cancelamento disponivel.

Riscos tecnicos:
- Equivalencia visual/tamanho com CRF nao identica.
- Limitacoes de codec/hardware por aparelho.
- Consumo de bateria/aquecimento.
- Pouco espaco em disco.

Dependencias:
- Android: Media3 Transformer, MediaCodec, MediaMuxer.
- iOS: AVFoundation.

## Perfis de compressao

Desktop:

| Nome | CRF | Preset | Descricao no codigo |
|---|---:|---|---|
| Alta Qualidade | 18 | `slow` | Menos compressao, maxima fidelidade visual |
| Balanceado | 23 | `medium` | Boa reducao com boa qualidade visual |
| Compressao Forte | 28 | `medium` | Foco em reducao agressiva |
| Compressao Maxima | 32 | `fast` | Maxima reducao (verificar qualidade) |

Android:
- Deve expor os mesmos nomes.
- Deve mapear para configuracoes nativas equivalentes apos testes.
- Fase 2 inicia com Balanceado; Fase 3 replica todos.

iOS:
- Deve expor os mesmos nomes.
- Mapeamento para presets/bitrate AVFoundation deve ser validado.

Diferencas inevitaveis:
- CRF/preset sao conceitos FFmpeg/libx264; APIs nativas nao oferecem equivalencia direta.

Criterios de aceite:
- Usuarios veem os mesmos perfis.
- Ordem e nomes preservados.
- Saidas respeitam gradiente: Alta Qualidade maior/melhor; Maxima menor/pior.

Riscos tecnicos:
- Tamanho final nao bater com desktop.
- Qualidade depender de hardware.

Dependencias:
- Testes comparativos por aparelhos.

## Alteracao de resolucao

Desktop:
- UI: `Original`, `1080p`, `720p`, `480p`.
- Mapeamento: Original `0`, demais alturas.
- FFmpeg: `scale=-2:altura`.
- Se rotacao for 90/270, compara resolucao com altura efetiva pos-rotacao.

Android:
- Deve manter as mesmas opcoes.
- Nativo deve configurar dimensoes de saida, mantendo proporcao e dimensoes pares quando exigido.

iOS:
- Deve manter as mesmas opcoes.
- AVFoundation deve aplicar transform/render size equivalente.

Diferencas inevitaveis:
- Desktop usa largura automatica `-2`; mobile deve calcular dimensoes.

Criterios de aceite:
- Original preserva resolucao quando escolhido.
- 1080p/720p/480p reduzem altura alvo mantendo proporcao.
- Saida compativel com MP4/H.264.

Riscos tecnicos:
- Orientacao/rotacao pode inverter largura e altura.
- Dimensoes impares podem falhar em codificadores.

Dependencias:
- Android: Media3/MediaCodec.
- iOS: AVMutableVideoComposition/AVAssetExportSession.

## Rotacao de video

Desktop:
- UI: `Sem rotacao`, `90 direita`, `90 esquerda`, `180`.
- Backend: `rotation` 0/90/270/180.
- Filtros:
  - 90 direita: `transpose=1`.
  - 90 esquerda: `transpose=2`.
  - 180: `hflip,vflip`.
- Rotacao entra antes do scale.

Android:
- Pode ser implementada por transformacao no pipeline Media3 ou matriz nativa.
- Deve manter os mesmos nomes.

iOS:
- Pode ser implementada por `preferredTransform`/video composition.

Diferencas inevitaveis:
- Mobile pode preferir metadata transform ou reencode; criterio deve exigir reproducao correta no arquivo final.

Criterios de aceite:
- Video final abre ja na orientacao escolhida.
- Scale continua correto quando combinado com rotacao.
- Original preservado.

Riscos tecnicos:
- Players podem interpretar metadata de rotacao de formas diferentes.
- Reencode pode ser necessario.

Dependencias:
- Android: Media3 Transformer ou pipeline com transform.
- iOS: AVFoundation.

## Remocao de audio

Desktop:
- Checkbox `Remover audio`.
- FFmpeg adiciona `-an`.
- Saida continua MP4.

Android:
- MediaMuxer/Media3 deve exportar apenas track de video.

iOS:
- AVAssetExport/Reader-Writer deve omitir tracks de audio.

Diferencas inevitaveis:
- Nativo opera por tracks, nao por flag `-an`.

Criterios de aceite:
- Saida sem faixa de audio.
- Video reproduz normalmente.
- Original preservado.

Riscos tecnicos:
- Arquivos sem audio devem continuar processando.

Dependencias:
- Android: MediaMuxer/Media3.
- iOS: AVFoundation.

## Extracao de audio

Desktop:
- UI possui botao `EXTRAIR MP3`.
- Nome de saida previsto: `{nome}_audio.mp3`.
- UI chama `VideoCompressor.extract_audio_mp3`.
- Backend ausente no `compressor.py` atual analisado; comportamento nao confirmado.

Android:
- Para MVP, nao deve ser implementada antes de corrigir/confirmar contrato.
- Extracao para MP3 nativa pode exigir encoder MP3 nao padrao; AAC/M4A e mais natural em APIs nativas.
- Se MP3 for obrigatorio, pode exigir FFmpeg/codec adicional/prova de conceito.

iOS:
- AVFoundation exporta audio com mais facilidade para M4A/AAC; MP3 nao e caminho nativo simples.
- MP3 exige avaliacao adicional.

Diferencas inevitaveis:
- MP3 nao e tao direto em APIs nativas mobile quanto MP4/AAC.

Criterios de aceite:
- Antes de implementar no mobile, desktop deve ter backend confirmado.
- Saida deve ser reproduzivel.
- Erro amigavel se nao houver audio.

Riscos tecnicos:
- Ausencia atual do metodo no backend desktop.
- Licenciamento/codec MP3 dependendo da abordagem.

Dependencias:
- Android/iOS: prova de conceito.
- Alternativa: exportar M4A no mobile e documentar diferenca, se aceitavel.

## Selecao da pasta de saida

Desktop:
- `_select_output_folder` usa `filedialog.askdirectory`.
- Label mostra `Pasta de saida definida`.
- Se nao selecionada, usa pasta do original.

Android:
- MVP pode salvar em cache/app-specific storage e oferecer compartilhar/salvar na galeria.
- Destino explicito deve usar Storage Access Framework ou MediaStore.

iOS:
- MVP pode salvar em app sandbox e usar Share Sheet/Photos.
- Destino explicito e mais restrito.

Diferencas inevitaveis:
- Mobile nao deve expor caminho livre como desktop.

Criterios de aceite:
- Usuario consegue salvar/compartilhar.
- Original preservado.

Riscos tecnicos:
- Permissoes e scoped storage.

Dependencias:
- Android: MediaStore, Share intents.
- iOS: Photos, Share Sheet.

## Progresso e cancelamento

Desktop:
- Progresso calculado por `time=` do `stderr` do FFmpeg.
- Cancelamento chama `terminate`, espera 5s e depois `kill`.

Android:
- Progresso deve vir do callback do motor nativo quando disponivel.
- Cancelamento deve cancelar job nativo e limpar arquivo parcial.

iOS:
- Progresso via export session/propria pipeline.
- Cancelamento via `cancelExport` ou controle do writer.

Diferencas inevitaveis:
- Modelo de progresso depende do motor nativo.

Criterios de aceite:
- UI nao trava.
- Barra avanca durante processamento.
- Cancelar interrompe e nao deixa resultado falso como sucesso.

Riscos tecnicos:
- Alguns motores nativos tem progresso impreciso.
- App em background pode ser suspenso.

Dependencias:
- Abstracao `VideoProcessingService`.

## Resultado final e abertura/salvamento

Desktop:
- Compressao mostra tamanho original, final, reducao e caminho.
- Extracao MP3 mostra tamanho do MP3 se backend funcionar.
- Ao confirmar sucesso, tenta abrir pasta.

Android:
- Mostrar antes/depois.
- Oferecer salvar/compartilhar.
- Exibir local amigavel, nao path tecnico.

iOS:
- Mostrar antes/depois.
- Oferecer salvar em Fotos/Arquivos e compartilhar.

Diferencas inevitaveis:
- Mobile usa intent/share sheet em vez de abrir pasta.

Criterios de aceite:
- Usuario entende onde ficou o arquivo.
- Compartilhamento funciona.

Riscos tecnicos:
- Salvar em galeria requer permissao/MediaStore/Photos.

Dependencias:
- Android: MediaStore, Share.
- iOS: Photos, Share Sheet.

## Validacao de FFmpeg

Desktop:
- `_check_ffmpeg` chama `is_ffmpeg_available`.
- Mostra instrucoes de instalacao se falhar.
- FFprobe nao e validado na UI, embora exista `is_ffprobe_available`.

Android:
- Nao assumir FFmpeg no sistema.
- Se usar motor nativo, validacao sera de capacidades do dispositivo.
- Se usar FFmpeg embarcado, validar presenca/licenca/tamanho.

iOS:
- Nao assumir FFmpeg no sistema.
- Preferir AVFoundation inicialmente.

Diferencas inevitaveis:
- Mobile nao tem binario FFmpeg externo instalado pelo usuario.

Criterios de aceite:
- App avisa quando formato/capacidade nao for suportado.

Riscos tecnicos:
- Dispositivos com codecs limitados.

Dependencias:
- Camada de capabilities no servico de video.
