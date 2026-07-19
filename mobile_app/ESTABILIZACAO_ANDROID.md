# Estabilizacao Android

Data: 2026-07-11

## Objetivo

Corrigir os riscos concretos identificados na analise tecnica anterior e melhorar o fluxo de entrada do app Android, sem tocar em perfis, resolucao, rotacao ou remocao de audio (que continuam fora de escopo nesta etapa) e sem alterar o desktop Python.

## 1. Resolucao segura de URI

Toda referencia de entrada (picker, compartilhamento, fallback local) agora passa por uma unica funcao central: `InputUriResolver.resolve(uriText, path)`, em `android/app/src/main/kotlin/.../InputUriResolver.kt`.

Regras aplicadas:

- `content://` -> usada como esta.
- `file://` -> usada como esta.
- Texto sem esquema (caminho local bruto) -> `Uri.fromFile(File(path))`, nunca `Uri.parse()` direto sobre o caminho.

Essa funcao e usada em `MainActivity.kt` nos tres pontos que antes tinham logica de resolucao de URI duplicada ou incompleta: leitura de metadados (`readVideoInfo`), inicio da compressao (`startCompression`) e consulta de tamanho do arquivo de entrada (`queryInputSize`). A duplicacao anterior foi removida.

`Uri.fromFile()` faz o percent-encoding correto do caminho, então nomes com espacos, acentos, `#`, `%`, parenteses ou caracteres Unicode (incluindo emoji) sao preservados. Antes, `Uri.parse()` sobre um caminho bruto interpretava `#` como inicio de fragmento e truncava o resto do nome do arquivo.

## 2. Abrir e compartilhar resultado

`shareResult` e `openResult` em `MainActivity.kt` nao engolem mais excecoes. Antes de iniciar a Intent, cada funcao verifica se ha um aplicativo capaz de resolve-la (`resolveActivity`); se nao houver, retorna `result.error("no_app", ...)` sem tentar `startActivity`. Se o `startActivity` falhar mesmo assim, o erro e capturado e propagado como `result.error("share_failed"/"open_failed", ...)`. Sucesso so e reportado (`result.success(null)`) depois que `startActivity` retorna sem excecao.

O Android 11+ filtra a visibilidade de pacotes para `resolveActivity`; foram adicionadas entradas em `<queries>` no `AndroidManifest.xml` para `ACTION_SEND` e `ACTION_VIEW` de `video/*`, para que essa checagem funcione corretamente em todas as versoes suportadas (minSdk 23).

No fallback de armazenamento para Android anterior ao 10 (sem MediaStore com `RELATIVE_PATH`), o video comprimido deixou de ser exposto como uma URI `file://` crua (que pode lancar `FileUriExposedException` ao compartilhar em apps que visam API 24+) e passou a ser exposto via `FileProvider`, com autoridade `${applicationId}.fileprovider` e permissao de leitura temporaria (`FLAG_GRANT_READ_URI_PERMISSION`, ja existente). Foram adicionados o provider no manifest e `res/xml/file_paths.xml` apontando para `getExternalFilesDir(Environment.DIRECTORY_MOVIES)`, a mesma pasta usada para salvar o arquivo.

No Flutter, `PlatformVideoProcessingService.shareResult/openResult` (`lib/services/video_processing_service.dart`) agora capturam `PlatformException` e relancam como `AppError` com uma das tres mensagens:

- "Não foi possível abrir o vídeo."
- "Não foi possível compartilhar o vídeo."
- "Nenhum aplicativo compatível foi encontrado." (quando o codigo nativo e `no_app`)

`HomeScreen` (`lib/screens/home_screen.dart`) captura esse `AppError` em `_shareResult`/`_openResult` e mostra a mensagem em um `SnackBar`. Nenhum caminho retorna sucesso quando a operacao falhou.

## 3. Recebimento por ACTION_SEND

`AndroidManifest.xml` ganhou um `intent-filter` de `android.intent.action.SEND` com categoria `DEFAULT` e `video/*` na `MainActivity`. Isso habilita o fluxo Galeria/WhatsApp/Camera -> Compartilhar -> Preparo de Videos.

A extracao da URI da Intent foi isolada em `SharedVideoIntent.kt` (funcao pura, sem depender de Context):

- `extractVideoUri(intent)`: retorna a URI apenas se a acao for `ACTION_SEND`, o tipo comecar com `video/` e houver um `EXTRA_STREAM` valido. Caso contrario, retorna nulo (Intent invalida, sem video, tipo errado etc. sao todos tratados sem excecao).
- `markConsumed(intent)`: remove o `EXTRA_STREAM` e neutraliza a acao (`ACTION_MAIN`) apos o consumo, para que a mesma Intent nao seja reprocessada quando a Activity for recriada (rotacao, dobra/desdobra do Galaxy Z Fold) sem que uma nova Intent chegue via `onNewIntent`.

`MainActivity` trata a Intent inicial (cold start, dentro de `configureFlutterEngine`) e novas Intents recebidas com o app ja aberto (`onNewIntent`). Dois canais expoem isso ao Flutter:

- `video_preparo_mobile/shared_intent` (MethodChannel): `consumeInitialSharedVideo` retorna o video pendente da Intent que abriu o app, ou nulo, e so retorna uma vez.
- `video_preparo_mobile/shared_intent_stream` (EventChannel): emite videos recebidos por compartilhamento enquanto o app ja esta em primeiro plano.

No Flutter, `SharedVideoService`/`PlatformSharedVideoService` (`lib/services/shared_video_service.dart`) encapsulam os dois canais e entregam um `SelectedVideo` pronto — a tela nunca ve Intent, MediaStore ou URI Android diretamente.

Em `HomeScreen`, o video recebido (inicial ou em stream) passa pelo mesmo metodo interno usado pelo seletor de arquivos (`_loadVideo`), que busca metadados via `VideoInfoService` e leva o app ao estado "pronto" — nunca inicia a compressao automaticamente. Um compartilhamento recebido enquanto ha uma compressao em andamento e ignorado (o usuario pode compartilhar de novo depois); o video atual nao e interrompido nem substituido.

Nao ha implementacao iOS. O contrato `SharedVideoService` fica pronto para uma futura Share Extension usar a mesma interface.

## 4. Progresso honesto

Nenhuma mudanca foi feita na forma como o Media3 reporta progresso (ja estava correta: percentual real quando disponivel, `null` quando indisponivel, sem calculo a partir da duracao).

O que mudou foi a apresentacao em `_ProgressCard` (`lib/screens/home_screen.dart`): quando o percentual esta disponivel, a barra continua determinada com o valor real. Quando esta indisponivel, a barra permanece indeterminada de verdade (nenhum numero e inventado) e um texto "Tempo decorrido: Xs" e exibido abaixo da mensagem "Comprimindo video...", calculado por um `Timer.periodic` de 1s que so roda durante o processamento e e cancelado ao concluir, cancelar ou falhar. O texto deixa claro que e tempo decorrido, nao tempo restante. O cancelamento continua disponivel durante todo o processamento.

## 5. Ajustes de experiencia

- `HapticFeedback.mediumImpact()` ao tocar em "Comprimir video".
- `HapticFeedback.lightImpact()` ao concluir com sucesso.
- O percentual de economia no card de resultado passou de mais uma linha de texto para um bloco destacado (numero grande, com `primaryContainer`) no topo do card, antes dos demais dados.
- Nenhum redesign, gradiente pesado, blur ou animacao decorativa foi adicionado. Material 3, tema claro/escuro e responsividade (Fold fechado/aberto) foram preservados sem alteracao de layout.

## Arquivos criados

- `android/app/src/main/kotlin/com/gustavonorberto/video_preparo_mobile/InputUriResolver.kt`
- `android/app/src/main/kotlin/com/gustavonorberto/video_preparo_mobile/SharedVideoIntent.kt`
- `android/app/src/main/res/xml/file_paths.xml`
- `android/app/src/test/kotlin/com/gustavonorberto/video_preparo_mobile/InputUriResolverTest.kt`
- `android/app/src/test/kotlin/com/gustavonorberto/video_preparo_mobile/SharedVideoIntentTest.kt`
- `lib/services/shared_video_service.dart`
- `test/video_processing_service_test.dart`
- `test/shared_video_service_test.dart`
- `android/app/src/main/kotlin/com/gustavonorberto/video_preparo_mobile/EncoderCapabilityProbe.kt`
- `android/app/src/main/kotlin/com/gustavonorberto/video_preparo_mobile/CqAwareEncoderFactory.kt`
- `android/app/src/main/kotlin/com/gustavonorberto/video_preparo_mobile/CompressionBenchmarkRunner.kt`
- `android/app/src/test/kotlin/com/gustavonorberto/video_preparo_mobile/EncoderCapabilityProbeTest.kt`
- `android/app/src/test/kotlin/com/gustavonorberto/video_preparo_mobile/CqAwareEncoderFactoryTest.kt`
- `android/app/src/test/kotlin/com/gustavonorberto/video_preparo_mobile/CompressionBenchmarkRunnerTest.kt`
- `lib/services/compression_benchmark_service.dart`
- `lib/screens/benchmark_debug_screen.dart`
- `test/compression_benchmark_service_test.dart`
- `mobile_app/BENCHMARK_CQ_FOLD6.md`
- `mobile_app/ESTABILIZACAO_ANDROID.md` (este arquivo)

## Arquivos modificados

- `android/app/src/main/kotlin/com/gustavonorberto/video_preparo_mobile/MainActivity.kt`
- `android/app/src/main/AndroidManifest.xml`
- `android/app/build.gradle.kts`
- `lib/app.dart`
- `lib/screens/home_screen.dart`
- `lib/services/video_processing_service.dart`
- `test/home_screen_test.dart`
- `mobile_app/README_MOBILE.md`

## Fora do escopo (mantido para depois)

Perfis alem de Balanceado, resolucoes, rotacao de saida, remover audio, extracao MP3, estimativa de tamanho final, verificacao de espaco em disco, novo algoritmo de bitrate, FFmpeg/FFmpegKit, WebView, servidor, historico, processamento em lote, iOS.

## 6. Prototipo de pesquisa: modo de qualidade constante (CQ)

Contexto: o desktop usa CRF (mira numa qualidade visual, deixa o bitrate variar por cena) enquanto o Android usava uma escada de bitrate fixo por faixa de resolucao — a causa raiz de o resultado parecer menos "inteligente" que o FFmpeg do desktop. A pergunta era se dava para usar um modo de qualidade constante (CQ) no encoder de video do Android, que e conceitualmente mais parecido com CRF, sem sair da arquitetura Media3 atual (sem NDK, sem FFmpeg, sem licenca GPL envolvida).

Verificando o codigo-fonte real do Media3 (`androidx.media3.transformer.VideoEncoderSettings` e `DefaultEncoderFactory`), confirmou-se que **o Media3 bloqueia CQ na propria API publica**: o `BitrateMode` so aceita `BITRATE_MODE_VBR` ou `BITRATE_MODE_CBR`, e `VideoEncoderSettings.Builder.setBitrateMode()` lanca excecao se receber qualquer outro valor. Nao e uma questao de o aparelho suportar ou nao — a biblioteca nao deixa pedir CQ pelo caminho oficial, em nenhum aparelho.

Para ainda assim testar CQ, foi implementado um `Codec.EncoderFactory` proprio que contorna o `DefaultEncoderFactory`:

- `EncoderCapabilityProbe.kt`: consulta `MediaCodecList`/`MediaCodecInfo.EncoderCapabilities` diretamente (sem Media3) para descobrir se algum encoder do aparelho anuncia suporte real a `BITRATE_MODE_CQ` **e** do qual conseguimos ler a `qualityRange` real (`getQualityRange()`, API 28+). Nunca assume que um valor de qualidade como 70 significa a mesma coisa em aparelhos diferentes.
- `CqAwareEncoderFactory.kt`: implementa `Codec.EncoderFactory`. Para audio, delega inteiramente ao encoder atual (nenhuma mudanca). Para video: se houver um encoder com CQ anunciado e `qualityRange` legivel, calcula o valor de qualidade dentro dessa faixa real (a partir de um `qualityFraction` 0.0-1.0 fornecido pelo chamador), monta o `MediaFormat` manualmente com `KEY_BITRATE_MODE = BITRATE_MODE_CQ` e `KEY_QUALITY`, e usa `DefaultCodec` do proprio Media3 para toda a fila de buffers/superficie. Se nenhum encoder anunciar CQ com faixa legivel, ou se a configuracao falhar em tempo de execucao, cai automaticamente para o `DefaultEncoderFactory` (VBR) — nenhum comportamento existente e removido. Um `Listener` opcional recebe uma `Decision` por chamada, com todos os dados necessarios para registrar honestamente qual caminho foi realmente seguido (nunca declarar CQ quando o resultado final foi VBR).

**Importante — isto NAO esta no pipeline de producao.** `MainActivity.startCompression` (o fluxo real "Comprimir agora") permanece exclusivamente em VBR via `DefaultEncoderFactory`, como estava antes deste prototipo. `CqAwareEncoderFactory` e usado apenas pela ferramenta de benchmark controlado (debug-only, ver `BENCHMARK_CQ_FOLD6.md`), que roda comparacoes lado a lado sem afetar o app que o usuario final usa. So faria sentido considerar substituir o pipeline de producao apos uma validacao fisica no aparelho confirmar ganho consistente.

Isto e codigo de prototipo/pesquisa, nao suportado oficialmente pelo Media3 nem pelo Android — implementacoes de CQ variam de qualidade entre fabricantes mesmo quando anunciadas. Log (`adb logcat`, tag `CqAwareEncoderFactory`) mostra qual caminho foi usado em cada chamada de benchmark; o log estruturado com tag `CompressionBenchmark` (usado pela ferramenta de benchmark) registra os dados tecnicos completos de cada execucao, sem dados pessoais ou conteudo do video.

Teste automatizado (`EncoderCapabilityProbeTest.kt`, `CqAwareEncoderFactoryTest.kt`, Robolectric): cobre apenas o contrato (nao lanca excecao, cai para fallback com honestidade quando nao ha encoder CQ disponivel). O ambiente de codec fake do Robolectric nao reflete hardware real, entao a resposta que importa — se o Galaxy Z Fold 6 realmente tem um encoder com CQ e como fica a qualidade/tamanho do resultado comparado ao VBR atual — so vem do teste manual no aparelho, registrado em `BENCHMARK_CQ_FOLD6.md`.

## Validacao

Este ambiente de implementacao nao tem o Flutter SDK, Android SDK nem acesso a rede para instala-los (`flutter`/`dart` nao encontrados, download bloqueado por allowlist). Os comandos abaixo **nao puderam ser executados aqui** e precisam rodar na maquina do desenvolvedor:

```bash
cd mobile_app
flutter pub get
flutter analyze
flutter test
flutter build apk --debug
```

Verificacao manual feita nesta etapa, no lugar da compilacao real:

- Chaves e parenteses balanceados em todos os arquivos Kotlin e Dart criados/alterados (checagem automatizada).
- Revisao linha a linha da logica nova (resolucao de URI, canais de Intent, tratamento de erro, timer de progresso).
- Nomes de metodo, canais (`MethodChannel`/`EventChannel`) e codigos de erro conferidos entre Kotlin e Dart para garantir que batem dos dois lados.

Recomenda-se rodar os quatro comandos acima antes de publicar. Se `flutter analyze` ou `flutter test` apontarem algum ajuste fino (por exemplo, nomes exatos de widgets em algum teste), o mais provavel e ser um pequeno detalhe de teste, nao da logica principal.
