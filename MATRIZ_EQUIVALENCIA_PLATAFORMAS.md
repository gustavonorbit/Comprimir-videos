# Matriz de Equivalencia entre Plataformas

Status: auditoria Fase 0. Mobile ainda nao implementado.

| Funcionalidade | Desktop atual | Android MVP | iOS futuro | Tecnologia Android sugerida | Tecnologia iOS sugerida | Pode ser identica? | Diferenca necessaria | Risco | Prioridade |
|---|---|---|---|---|---|---|---|---|---|
| Selecao de video | `filedialog.askopenfilename` com extensoes de video | Photo Picker/SAF; selecionar galeria/arquivos | Photos/document picker | Flutter UI + Android Photo Picker/Storage Access Framework | Flutter UI + Photos framework/document picker | Nao | Desktop usa path; mobile usa URI/permissao | Medio | Alta |
| Leitura de tamanho | `os.path.getsize` | Tamanho via ContentResolver ou copia local | File attributes/asset resource | ContentResolver, DocumentFile | Foundation/Photos | Parcial | URI pode nao ter path direto | Medio | Alta |
| Leitura de duracao/resolucao | FFprobe stream `width,height,duration` | Ler metadata | Ler metadata | MediaMetadataRetriever | AVAsset | Parcial | Metadados podem divergir por orientacao/container | Medio | Alta |
| Compressao MP4 | FFmpeg `libx264`, CRF/preset, MP4 | Exportar MP4 H.264 | Exportar MP4 H.264 | AndroidX Media3 Transformer, MediaCodec, MediaMuxer | AVAssetExportSession, AVAssetReader/Writer | Nao | CRF/preset nao sao equivalentes nativos | Alto | Alta |
| Perfil Alta Qualidade | CRF 18, preset slow | Perfil equivalente por bitrate/qualidade apos POC | Perfil equivalente por preset/bitrate apos POC | Media3/MediaCodec config | AVFoundation export/writer config | Nao | Mapear qualidade por testes | Alto | Media |
| Perfil Balanceado | CRF 23, preset medium | Primeiro perfil MVP | Futuro primeiro perfil | Media3 Transformer | AVAssetExportSession | Nao | Mapear para bitrate/preset nativo | Alto | Alta |
| Perfil Compressao Forte | CRF 28, preset medium | Fase 3 | Fase 6 | Media3/MediaCodec | AVFoundation | Nao | Validacao visual/tamanho | Alto | Media |
| Perfil Compressao Maxima | CRF 32, preset fast | Fase 3 | Fase 6 | Media3/MediaCodec | AVFoundation | Nao | Pode gerar artefatos diferentes | Alto | Media |
| Alteracao resolucao | FFmpeg `scale=-2:altura` | Calcular output size e reencode | Render size/video composition | Media3 effects/MediaCodec | AVMutableVideoComposition/AVAssetWriter | Parcial | Mobile deve calcular largura par | Medio | Alta |
| Rotacao 90 direita | `transpose=1` | Transformacao/reencode | Transform/video composition | Media3 Transformer effects ou Matrix | AVMutableVideoComposition/preferredTransform | Parcial | Metadata vs pixels reais deve ser decidido | Medio | Media |
| Rotacao 90 esquerda | `transpose=2` | Transformacao/reencode | Transform/video composition | Media3 Transformer effects ou Matrix | AVMutableVideoComposition/preferredTransform | Parcial | Metadata vs pixels reais deve ser decidido | Medio | Media |
| Rotacao 180 | `hflip,vflip` | Transformacao 180/reencode | Transform 180/video composition | Media3 effects/Matrix | AVMutableVideoComposition | Parcial | Implementacao nativa difere do filtro FFmpeg | Medio | Media |
| Remover audio | FFmpeg `-an` | Omitir track de audio | Omitir track de audio | MediaMuxer/Media3 track selection | AVAssetReader/Writer sem audio | Sim no resultado | Implementacao por tracks | Baixo/medio | Alta |
| Manter audio | `-c:a aac -b:a 128k` | Manter ou reencodar audio | Manter ou reencodar audio | MediaCodec AAC/Media3 | AVFoundation AAC | Parcial | Bitrate pode divergir | Medio | Alta |
| Extrair audio MP3 | UI chama metodo ausente; backend nao confirmado | Nao no MVP; exige POC | Nao no MVP; exige POC | FFmpeg/encoder MP3 ou alternativa M4A | AVFoundation M4A; MP3 exige alternativa | Nao | MP3 nao e nativo simples | Alto | Baixa antes de corrigir desktop |
| Nome de saida compressao | `{stem}_comprimido.mp4` | Nome equivalente ou amigavel no app storage | Nome equivalente ou amigavel no sandbox | Dart path utils + MediaStore | Dart path utils + Files/Photos | Parcial | Mobile pode nao expor pasta original | Medio | Alta |
| Pasta de saida padrao | Pasta do original | App storage/cache + salvar/compartilhar | Sandbox + salvar/compartilhar | MediaStore, SAF, Share intent | Photos, UIDocumentPicker, Share Sheet | Nao | Mobile nao usa pasta arbitraria por padrao | Medio | Alta |
| Confirmar sobrescrita | `messagebox.askyesno` | Evitar sobrescrita ou confirmar destino | Evitar sobrescrita ou confirmar destino | Flutter dialog | Flutter/Cupertino dialog | Sim conceitualmente | Storage mobile pode gerar nomes unicos | Baixo | Media |
| Progresso | Parse de `stderr time=` | Callback/progress do motor | Export progress | Media3 progress/listener ou job polling | AVAssetExportSession.progress | Parcial | Fonte do progresso muda | Medio | Alta |
| Cancelamento | `terminate`/`kill` subprocess | Cancelar job nativo | Cancelar export/job | Media3 cancellation/coroutines | `cancelExport`/task cancel | Parcial | Limpeza de parcial precisa ser implementada | Medio | Alta |
| Validacao FFmpeg | `ffmpeg -version` | Nao aplicavel se motor nativo | Nao aplicavel se AVFoundation | Capabilities check | Capabilities check | Nao | Mobile valida capacidades, nao binario externo | Medio | Alta |
| Abrir pasta de saida | Windows `os.startfile`; POSIX `open` | Compartilhar/salvar | Share Sheet/Salvar em Fotos | Android share/MediaStore | UIActivityViewController/Photos | Nao | Mobile nao abre pasta | Baixo | Alta |
| Preservar original | Gera novo arquivo separado | Obrigatorio | Obrigatorio | Copia/cache/output separado | Sandbox/output separado | Sim | URIs exigem cuidado | Medio | Alta |
| Erros amigaveis | `messagebox` + status | Snack/dialog/tela de erro | Snack/dialog/tela de erro | Flutter | Flutter | Sim conceitualmente | Textos e permissoes especificos | Baixo | Alta |
| Corte futuro | Nao implementado | Pode ser nativo | Pode ser nativo | Media3 clipping/MediaExtractor | AVAssetExportSession timeRange | Nao aplicavel | Funcao futura | Medio | Media |
| Blur futuro | Nao implementado | Exige pipeline de efeito/reencode | Exige video composition/Core Image | Media3 effects/OpenGL/Shader/FFmpeg POC | Core Image/AVVideoComposition | Nao | Alta complexidade | Alto | Media |

## Avaliacao do motor de video por funcao

| Funcao | Android | iOS | Classificacao |
|---|---|---|---|
| Compressao MP4 | Suportada nativamente com Media3/MediaCodec, mas sem equivalencia direta de CRF | Suportada com AVFoundation, sem equivalencia direta de CRF | Suportada nativamente; precisa POC de equivalencia |
| Conversao para MP4 | Suportada para formatos decodificaveis pelo dispositivo | Suportada para formatos aceitos pelo AVFoundation | Suportada nativamente com limitacoes |
| Rotacao | Suportada via transform/effect | Suportada via transform/video composition | Suportada nativamente; precisa definir metadata vs pixels |
| Remocao de audio | Suportada omitindo track | Suportada omitindo track | Suportada nativamente |
| Extracao de audio | AAC/M4A nativo viavel; MP3 exige POC/alternativa | M4A nativo viavel; MP3 exige POC/alternativa | MP3 exige FFmpeg ou alternativa; precisa POC |
| Alteracao de resolucao | Suportada por reencode nativo | Suportada por export/video composition | Suportada nativamente; precisa POC |
| Corte futuro | Suportado por clipping/extractor | Suportado por timeRange | Suportada nativamente |
| Leitura de metadados | Suportada | Suportada | Suportada nativamente |
| Progresso | Depende do motor, geralmente possivel | Export session tem progress; writer manual exige controle | Suportada, com precisao variavel |
| Cancelamento | Depende do job/pipeline | Suportado em export; manual exige controle | Suportada com codigo nativo adicional |

## Decisao preliminar

- Android MVP deve validar Media3 Transformer antes de considerar FFmpeg mobile.
- iOS futuro deve validar AVFoundation antes de considerar FFmpeg.
- Extracao MP3 nao deve entrar no MVP mobile ate o contrato desktop estar consistente e a viabilidade nativa/codec ser provada.
- A UI Flutter deve depender somente de `VideoProcessingService`, sem conhecer Media3, MediaCodec, AVFoundation ou FFmpeg.
