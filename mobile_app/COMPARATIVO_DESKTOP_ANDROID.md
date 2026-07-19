# Comparativo forense: desktop (FFmpeg/libx264) vs Android (Media3/MediaCodec)

## Contexto

A POC de modo de qualidade constante (CQ) no Android foi concluída e está **reprovada** no
Galaxy Z Fold 6 testado: nenhum dos 3 modos CQ obteve suporte real do encoder (`suporteDeclaradoCq:
false`, `qualityRange` indisponível), todos os 3 caíram para VBR (`fallbackExecutado: true`), e o
resultado observado (~113 MB, ~3012 kbps, ~78,2% de redução) é o resultado do VBR de produção, não
de CQ. Nenhum ganho foi obtido por essa via neste aparelho. Ver seção "Encerramento da POC CQ".

Esta etapa não investiga mais CQ. O objetivo agora é entender, com dados reais lidos do código
(nunca supostos), por que o desktop historicamente produz arquivos muito menores que o Android, e
se isso é resolvível ajustando o Media3 ou exige encoding por software (NDK/libx264).

**Nenhum comportamento de produção foi alterado nesta etapa** (nem Android, nem desktop). Este
documento é apenas leitura/medição.

## Tarefa 1 — Perfil real de maior compressão do desktop

Lido diretamente de `compressor.py` (`COMPRESSION_PROFILES["Compressão Máxima"]` e
`compress_video`), sem interpretar nomes — valores reais:

| Parâmetro | Valor real |
|---|---|
| CRF | `32` |
| Preset | `fast` |
| Codec de vídeo | `libx264` |
| Codec de áudio | `aac` |
| Bitrate de áudio | `128k` (fixo, não depende do perfil) |
| Resolução | Original, a menos que o usuário escolha outra no combo `combo_resolution` (padrão da UI: `"Original"` → `resolution=0` → nenhum filtro de escala aplicado) |
| Filtro de escala | Nenhum quando a resolução pedida é a original; caso contrário `scale=-2:{altura_alvo}` (mantém proporção, `-2` força largura par) |
| FPS | Não alterado — não existe nenhuma flag `-r`/`-fps` no código; o FFmpeg preserva o frame rate de entrada |
| Pixel format | Não especificado explicitamente (sem `-pix_fmt` no comando); fica a critério do padrão do `libx264` para entrada 8-bit, que é `yuv420p` (confirmado no teste real abaixo) |
| Tune | Não definido (sem `-tune`) |
| Profile (H.264) | Não definido (sem `-profile:v`); o `libx264` escolhe automaticamente (confirmado no teste real: `High`) |
| Level (H.264) | Não definido (sem `-level`); automático (confirmado no teste real: `4.0`) |
| Faststart | Sim — `-movflags +faststart` |
| Áudio removido | Só se o usuário marcar o checkbox "Remover áudio" (`ctk.CTkCheckBox` sem `.select()` no construtor, ou seja, **desmarcado por padrão** → áudio é mantido por padrão) |
| Rotação | Só se o usuário escolher rotação manual (`combo_rotation`, padrão `"Sem rotação"` → nenhum filtro de rotação) |
| Sobrescrita | `-y` (sobrescreve sem perguntar) |

### Comando FFmpeg real (caso comum: resolução original, sem rotação, áudio mantido)

```bash
ffmpeg -i <input_file> \
  -c:v libx264 -crf 32 -preset fast \
  -c:a aac -b:a 128k \
  -movflags +faststart \
  -y <output_file>
```

Se o usuário pedir outra resolução e/ou rotação, o único acréscimo é uma flag `-vf` antes de
`-c:v`, combinando o filtro de rotação (`transpose=1`/`hflip,vflip`/`transpose=2`) e o filtro de
escala (`scale=-2:{altura}`), separados por vírgula. Se "Remover áudio" estiver marcado, o bloco de
áudio vira apenas `-an`.

## Tarefa 2 — Execução no desktop

**Limitação importante, registrada com transparência**: o vídeo real usado no teste do Android
(~497 MB, ~5:01, 1920×1080, 30 FPS) existe apenas no computador/celular do usuário — não estava
disponível nem na pasta conectada (`Comprimir videos`) nem em nenhum upload deste ambiente. Não é
possível "inventar" esse arquivo nem seu resultado. Diante disso, foram apresentadas opções e o
usuário escolheu explicitamente gerar um **clipe sintético equivalente em resolução/FPS**, apenas
para validar que o comando do perfil "Compressão Máxima" funciona como documentado — **os números
de tamanho/redução deste teste NÃO devem ser lidos como uma previsão do resultado no vídeo real**.

### Geração do clipe sintético de entrada

```bash
ffmpeg -f lavfi -i "testsrc2=size=1920x1080:rate=30,noise=alls=20:allf=t+u" \
  -f lavfi -i "sine=frequency=440:sample_rate=48000" \
  -t 10 -pix_fmt yuv420p -c:v libx264 -preset veryfast -crf 15 \
  -c:a aac -b:a 192k -ac 2 \
  -y synthetic_input.mp4
```

Padrão de teste (`testsrc2` + ruído por pixel) escolhido por ser rápido de gerar neste ambiente e
por não ser trivialmente compressível (ao contrário de um gradiente liso) — ainda assim, ruído
sintético comprime de forma muito diferente de vídeo de câmera real (motion blur, ruído de sensor,
compressão temporal entre quadros parecidos). Duração reduzida para 10s (não 5:01) por limite de
tempo de execução deste ambiente sandbox.

`ffprobe` da entrada sintética:

```json
{
  "video": {"codec_name": "h264", "width": 1920, "height": 1080, "pix_fmt": "yuv420p",
             "r_frame_rate": "30/1", "duration": "10.000000", "bit_rate": "174720415"},
  "audio": {"codec_name": "aac", "sample_rate": "48000", "channels": 2, "bit_rate": "61273"},
  "format": {"duration": "10.000000", "size": "218489504", "bit_rate": "174791603"}
}
```

### Execução do comando real do perfil "Compressão Máxima"

```bash
ffmpeg -i synthetic_input.mp4 \
  -c:v libx264 -crf 32 -preset fast \
  -c:a aac -b:a 128k \
  -movflags +faststart \
  -y desktop_max_output.mp4
```

Tempo de execução medido (`time`): **11,02 s reais** (10 s de conteúdo sintético; `user` 37,95 s
somando threads). Não comparável ao tempo real de um vídeo de 5 minutos.

`ffprobe` da saída:

```json
{
  "video": {"codec_name": "h264", "profile": "High", "level": 40, "width": 1920, "height": 1080,
             "pix_fmt": "yuv420p", "r_frame_rate": "30/1", "duration": "10.000000",
             "bit_rate": "1881799"},
  "audio": {"codec_name": "aac", "sample_rate": "48000", "channels": 2,
             "duration": "10.005000", "bit_rate": "60923"},
  "format": {"duration": "10.006000", "size": "2439262", "bit_rate": "1950239"},
  "rotate_tag": "ausente (nenhuma rotação aplicada)"
}
```

Tamanho final: 2.439.262 bytes (~2,33 MiB). Redução: ~98,9% frente à entrada sintética (não
representativo do vídeo real — ver limitações). Resolução, FPS e presença de áudio preservados.
Profile/level (`High`/`4.0`) e pixel format (`yuv420p`) confirmados como escolhidos automaticamente
pelo `libx264`, já que o comando real não os define explicitamente.

**Observação sobre o áudio**: o comando pede `-b:a 128k`, mas o `ffprobe` da saída mediu ~60,9
kbps. Não altero nem reinterpreto esse número — está registrado como medido. É consistente com o
conteúdo de entrada ser um tom senoidal simples (baixíssima entropia para o codificador AAC), não
com uma falha do comando. Não valido essa taxa como "o que aconteceria com áudio real de câmera".

**Qualidade visual observada pelo usuário**: não avaliada — o clipe é sintético (ruído + padrão de
teste), não há como avaliar "qualidade percebida" de forma significativa nele.

## Tarefa 3 — Comparação direta

| Métrica | Original | Desktop máximo | Android VBR |
|---|---:|---:|---:|
| Tamanho | ~497 MB (real, informado) / 218,49 MB (sintético) | 2,33 MB (**sintético — não extrapolar**) | ~113 MB (real, Fold 6) |
| Resolução | 1920×1080 (informado/sintético) | 1920×1080 (preservada) | 1920×1080 (preservada, `resolutionPolicy=Original`) |
| FPS | 30 (informado/sintético) | 30 (preservado) | 30 (preservado) |
| Codec | não confirmado no real / h264 (sintético) | h264, libx264, profile High, level 4.0 | h264, MediaCodec de hardware (profile/level não configurados pelo app) |
| Bitrate de vídeo | não medido no real / ~174,72 Mbps (sintético, artificialmente alto por ser quase incompressível) | ~1,88 Mbps (sintético) | ~2,2 Mbps solicitado à escada automática de 1080p (bitrate médio final total, vídeo+áudio+contêiner, informado pelo usuário: ~3012 kbps) |
| Bitrate de áudio | ~61,27 kbps (sintético) | ~60,92 kbps medido (alvo pedido: 128k) | não configurado explicitamente no código Android (`DefaultEncoderFactory` usa o padrão do Media3 para AAC — nenhum `AudioEncoderSettings` é definido em `MainActivity.startCompression`) |
| Duração | ~5:01 (real) / 10,000 s (sintético) | 10,000 s preservada | ~5:01 preservada (real) |
| Tempo de processamento | – | 11,02 s p/ 10 s sintéticos (não comparável) | não informado neste resultado |
| Redução | – | ~98,9% (**sintético, não representativo**) | ~78,2% (real, Fold 6) |

### Respostas objetivas

1. **O desktop mantém 1920×1080?** Sim — confirmado no código (`resolution=0`/`"Original"` não
   adiciona `-vf scale`) e no teste real do comando (saída manteve 1920×1080).
2. **O desktop mantém 30 FPS?** Sim — não há nenhuma flag de FPS no comando; confirmado no teste
   (saída manteve 30/1).
3. **O desktop mantém áudio?** Sim, por padrão — o checkbox "Remover áudio" começa desmarcado;
   áudio é reencodado em AAC 128k a menos que o usuário marque removê-lo.
4. **O tamanho de ~5 MB acontece com este mesmo vídeo?** Não verificável neste ambiente — o
   arquivo real de 497 MB não estava disponível para teste. A alegação permanece **não confirmada**
   até ser medida com o arquivo real.
5. **Quanto da diferença vem de resolução/FPS/áudio?** Zero. Resolução, FPS e presença de áudio são
   idênticos entre entrada e saída nos dois pipelines (real e sintético); nenhuma parte de qualquer
   diferença de tamanho vem dessas variáveis.
6. **Quanto vem da eficiência do libx264?** Não é possível quantificar com precisão sem rodar o
   vídeo real nos dois lados. Estruturalmente, a diferença provável está no modelo de controle de
   taxa: CRF (alvo de qualidade perceptual, bitrate variável por cena, com as otimizações
   psicovisuais do `libx264`) contra bitrate-alvo fixo do Android (VBR do `MediaCodec`, sem o mesmo
   tipo de adaptação por complexidade de cena).
7. **O Android poderia reproduzir isso só ajustando Media3?** Parcialmente, no máximo. A API
   pública do Media3 só aceita `BITRATE_MODE_VBR` ou `BITRATE_MODE_CBR` (confirmado por
   código-fonte na etapa anterior) — não há um modo CRF-like oficial. E, especificamente no Fold 6
   testado, nem a alternativa parcial (CQ real) está disponível, porque nenhum encoder do aparelho
   anunciou suporte.
8. **Ou software encoding é realmente necessário?** Com os dados atuais, software encoding (ou
   outra biblioteca com controle de taxa por qualidade real) é a única via confirmada para
   reproduzir o modelo CRF no Android. Mas isso ainda **não foi comprovado como necessário para
   este vídeo especificamente**, porque a comparação real (mesmo arquivo, desktop vs Android) ainda
   não foi feita.

## Tarefa 4 — Decisão técnica

Nenhuma das quatro alternativas pode ser marcada como conclusão fechada, porque a Tarefa 2 não
rodou no arquivo real:

- **Não é A** — o desktop não reduz resolução/FPS (ambos preservam, confirmado).
- **Não posso confirmar B com números reais** — a estrutura de código aponta para essa direção
  (CRF adaptativo vs bitrate fixo), mas isso é uma hipótese fundamentada em arquitetura, não uma
  medição do mesmo arquivo nos dois lados.
- **Parcialmente C** — a alegação de "~5 MB" não pôde ser reproduzida (nem confirmada, nem
  refutada) neste vídeo, porque o arquivo real não estava disponível.
- **Não é D** — não foi possível avaliar qualidade visual do desktop no vídeo real.

**Recomendação**: antes de abrir um estudo de NDK/libx264 (ou de fechar a meta de "~5 MB" como
real), rodar o comando exato da Tarefa 1 no arquivo real de 497 MB (no computador do usuário, que
tem FFmpeg conforme `README.md`/`requirements.txt`) e registrar os mesmos campos desta tabela. Só
com esse dado real dá para classificar com segurança em B, C ou D.

## Encerramento da POC CQ

- CQ **não é suportado** pelo(s) encoder(s) do Galaxy Z Fold 6 testado (`suporteDeclaradoCq:
  false`, `qualityRange` indisponível).
- Todos os 3 modos CQ (conservador/agressivo/extremo) caíram para VBR (`fallbackExecutado: true`).
- **Nenhum ganho foi obtido** por CQ neste aparelho — o resultado observado é puramente do VBR de
  produção.
- A POC **não deve permanecer no produto release**. Hoje ela já não vaza para release (gate duplo:
  `kDebugMode` no Flutter + `BuildConfig.DEBUG` no canal nativo), mas o código-fonte experimental
  (`CqAwareEncoderFactory.kt`, os métodos de `EncoderCapabilityProbe.kt` específicos de CQ,
  `CompressionBenchmarkRunner.kt`, `compression_benchmark_service.dart`,
  `benchmark_debug_screen.dart`, o botão em `home_screen.dart` e os testes associados) deve ser
  removido numa tarefa separada, após aprovação, para não virar código morto.
- **Esta tarefa não removeu nada** — apenas documentou o encerramento, conforme instruído
  ("não remover imediatamente... após decisão aprovada, preparar uma tarefa separada").

## Limitações da medição

- O vídeo real de 497 MB/5:01/1920×1080/30 FPS não estava disponível neste ambiente (nem na pasta
  conectada, nem em upload); os números de "Desktop máximo" nesta rodada vêm de um clipe sintético
  gerado sob escolha explícita do usuário, apenas para validar a mecânica do comando (preserva
  resolução/FPS/áudio/pixel format, produz um MP4 válido com faststart, não trava).
- Conteúdo sintético (padrão de teste + ruído por pixel) tem características de compressão muito
  diferentes de vídeo de câmera real; a redução de ~98,9% medida aqui **não** deve ser comparada
  com a redução de ~78,2% do Android, nem usada para prever o resultado real do desktop.
- Duração do clipe sintético reduzida para 10 s (não 5:01) por limite de tempo de execução deste
  ambiente sandbox; "tempo de processamento" medido não é comparável ao tempo real de um vídeo de 5
  minutos.
- O bitrate de áudio medido na saída (~60,9 kbps) ficou abaixo do alvo pedido (128k) — atribuído ao
  conteúdo de áudio sintético (tom senoidal simples), não a um problema do comando; não investigado
  mais a fundo por não ser relevante para a pergunta central desta etapa.
- Nenhuma qualidade visual foi avaliada (nem do lado desktop, nem repetição do lado Android) — a
  avaliação visual do desktop com o vídeo real ainda precisa ser feita manualmente, como já é
  prática estabelecida para o benchmark Android.
- A tabela usa `~113 MB`/`~3012 kbps`/`~78,2%` para "Android VBR" exatamente como informado pelo
  usuário a partir do resultado do benchmark no Fold 6; não foram re-executados nem re-verificados
  nesta etapa.
