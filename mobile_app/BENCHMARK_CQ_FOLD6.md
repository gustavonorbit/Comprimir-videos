# Benchmark controlado: VBR atual vs. CQ experimental (Galaxy Z Fold 6)

## Objetivo

Comparar, no mesmo aparelho e com o mesmo arquivo de video, o pipeline de producao atual (VBR,
via `DefaultEncoderFactory`) contra 3 configuracoes internas de modo de qualidade constante (CQ,
via `CqAwareEncoderFactory`), para decidir com evidencia empirica — nao suposicao — se vale a pena
seguir investindo em CQ como alternativa ao VBR.

**Este benchmark nao adiciona escolha de qualidade a UI publica do app.** E uma ferramenta interna,
debug-only, usada apenas para gerar os dados desta comparacao.

## Importante sobre os valores de CQ

O valor de qualidade (`KEY_QUALITY`) usado em cada modo CQ **nao e um numero fixo**. Ele e
calculado, em tempo de execucao, dentro da `qualityRange` real que o encoder do proprio Fold 6
declara (`MediaCodecInfo.EncoderCapabilities.getQualityRange()`). O mesmo "70" pode significar
niveis de compressao completamente diferentes em aparelhos diferentes — por isso o app le a faixa
real antes de escolher um valor, em vez de assumir uma escala universal.

As 3 configuracoes de CQ pedem uma fracao dessa faixa real (0.0 = extremo inferior da faixa, mais
compressao; 1.0 = extremo superior, mais qualidade):

| Config interna | Fracao da qualityRange real | Intencao |
|---|---|---|
| CQ conservador | 0.85 | Prioriza qualidade, ganho de compressao menor |
| CQ agressivo | 0.50 | Meio-termo |
| CQ extremo | 0.15 | Prioriza reducao de tamanho, risco maior de perda visual |

O modo VBR atual (controle) usa exatamente a mesma escada de bitrate que a compressao automatica
de producao (`AutomaticCompressionStrategy.buildMaximumCompressionSettings`), garantindo que a
comparacao seja "app real vs. experimento", nao "duas configuracoes arbitrarias".

## Como acessar a ferramenta

1. Rodar o app em build debug (`flutter run`, ou instalar um `flutter build apk --debug`). O botao
   **nunca aparece em build release** — o ponto de entrada e eliminado em tempo de compilacao pelo
   Flutter (`kDebugMode`) e o canal nativo tambem recusa qualquer chamada quando
   `BuildConfig.DEBUG` for falso, como garantia dupla.
2. Selecionar o video de teste na tela principal (nao precisa comprimir antes).
3. Na secao "Opções extras", tocar em **"Benchmark CQ (debug)"**.
4. Na tela de benchmark, tocar em "Rodar" em cada um dos 4 modos, um de cada vez (nao ha execucao
   em lote automatica — cada modo e uma compressao completa e precisa ser disparada manualmente).
5. Copiar os valores retornados por cada execucao para a tabela abaixo.

## Campos registrados por execucao

Cada execucao grava uma linha de log estruturada (`adb logcat -s CompressionBenchmark`) e retorna
o mesmo conjunto de dados para a tela de benchmark, incluindo: modo solicitado, modo realmente
utilizado, nome do encoder, MIME de saida, se o aparelho declara suporte real a CQ, a
`qualityRange` real do encoder, a qualidade solicitada, tamanho original e final, percentual de
reducao, duracao do video, tempo total de processamento, resolucao, FPS, bitrate medio final,
sucesso/erro e mensagem tecnica de falha quando aplicavel.

A "qualidade efetiva" (o valor de `KEY_QUALITY` realmente aplicado durante a codificacao) chega
sempre como indisponivel: o Android nao expõe uma API publica de leitura desse valor apos a
codificacao. Reportamos apenas a qualidade solicitada, nunca inventamos um valor "efetivo".

Os logs (`adb logcat`) **nao incluem** a URI do video, o caminho do arquivo, o nome de exibicao,
nem qualquer conteudo do video — apenas os campos tecnicos acima.

## Preparo do teste fisico

- Usar o mesmo video em todas as 8 execucoes (4 modos, idealmente 2 rodadas para checar
  repetibilidade): ~497 MB, ~5 minutos, 1920x1080.
- Aparelho carregando ou com bateria suficiente para o teste completo.
- Deixar o aparelho esfriar entre execucoes (varios minutos, tela desligada) para nao distorcer o
  tempo de processamento por causa de thermal throttling. Se o aparelho estiver visivelmente quente
  ao toque antes de uma execucao, aguardar mais antes de continuar.
- Rodar os 4 modos na mesma sessao de temperatura ambiente, se possivel, para que a comparacao de
  tempo entre eles seja justa.

## Tabela de resultados (preencher apos o teste no aparelho)

| Modo | Encoder | CQ real? | Qualidade | Tempo | Tamanho | Redução | Bitrate final | Fallback | Avaliação visual |
|---|---|---|---|---|---|---|---|---|---|
| VBR atual (controle) | | | | | | | | | |
| CQ conservador | | | | | | | | | |
| CQ agressivo | | | | | | | | | |
| CQ extremo | | | | | | | | | |

Legenda rapida:
- **CQ real?**: "sim" somente se `modoUtilizado` retornou `cq` (nunca marcar sim se
  `fallbackExecutado` for verdadeiro — isso indica que o pipeline caiu para VBR apesar de CQ ter
  sido solicitado).
- **Qualidade**: o valor de `qualidadeSolicitada` e a `qualityRange` real reportada (ex: `62 (faixa
  0-100)`), para dar contexto a esse numero.
- **Avaliação visual**: preenchida manualmente, comparando o arquivo de saida de cada modo lado a
  lado (nao ha metrica automatica de qualidade percebida nesta ferramenta).

## Critério de decisão

CQ so deve substituir VBR no pipeline de produção se, nos testes físicos, **todos** os pontos
abaixo forem verdadeiros:

- Resultado repetível entre rodadas (mesma configuração produz tamanho/tempo semelhantes).
- Nenhum arquivo inválido ou corrompido gerado.
- Redução de tamanho significativamente maior que o VBR atual, no mesmo nível de qualidade visual
  aceitável.
- Qualidade visual aceitável (avaliação manual).
- Tempo de processamento e geração de calor em níveis práticos para uso real (não apenas
  tecnicamente possível em condições ideais de laboratório).
- O fallback para VBR funciona corretamente quando CQ não está disponível ou falha.

Se qualquer um desses critérios falhar, a conclusão é: remover o protótipo de CQ (não deixar como
código morto/abandonado) e manter VBR em produção, avaliando outras tecnologias caso o ganho de
qualidade ainda seja considerado necessário.

## Validação local (antes do teste físico)

Comandos a rodar na máquina de desenvolvimento (este ambiente de implementação não tem Flutter/
Android SDK nem acesso à rede para instalá-los — não foi possível rodá-los aqui):

```bash
cd mobile_app
flutter pub get
flutter analyze
flutter test
flutter build apk --debug
```

Testes Gradle/Kotlin aplicáveis (rodar via Android Studio ou `./gradlew testDebugUnitTest` dentro
de `mobile_app/android`, quando o ambiente tiver o Android SDK):

- `EncoderCapabilityProbeTest`
- `CqAwareEncoderFactoryTest`
- `CompressionBenchmarkRunnerTest`

Qualquer erro real de compilação apontado por esses comandos deve ser corrigido antes do teste
físico no Fold 6 — o benchmark só tem valor se o app compilar e rodar corretamente.

Verificação manual feita nesta etapa, no lugar da compilação real: chaves e parênteses balanceados
em todos os arquivos Kotlin/Dart novos e alterados; nomes de canal, método e chaves do mapa de
resultado conferidos entre `MainActivity.kt`/`CompressionBenchmarkRunner.kt` e
`compression_benchmark_service.dart` (`video_preparo_mobile/compression_benchmark`,
`runBenchmark`, e as ~20 chaves do resultado, uma a uma).
