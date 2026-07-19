# Análise: App Mobile Android (`mobile_app`)

Escopo desta análise: apenas o app Flutter/Android (`lib/`, `android/app`), conforme pedido. Desktop ignorado aqui.

## 1. Por que "não aparece dropdown de compressão" no Android

No Android isso não é bug de renderização — hoje **não existe nenhum controle editável de compressão na tela**. Em `home_screen.dart`, `_settings` é criado uma única vez com `CompressionSettings.balancedOriginal()` e nunca é alterado por nenhum widget; o card "Opções de compressão" apenas exibe texto fixo (Balanceado / Original / Sem rotação / Áudio mantido) com o aviso "Primeiro recorte Android: perfil Balanceado...". Isso é intencional e está documentado em `IMPLEMENTACAO_FASE_2.md` e no `ROADMAP_MOBILE.md`: o projeto está propositalmente na Fase 2 (só compressão Balanceado), e perfis/resolução/rotação/remover áudio ficam para as Fases 3 e 4. Ou seja, não há dropdown quebrado — há uma tela que ainda não implementa a escolha, o que pode passar a impressão de "faltando algo" para quem usa o app sem saber do roadmap.

Se a intenção é acelerar isso, a ordem recomendada pelo próprio roadmap (Fase 3 → perfis, Fase 4 → resolução/rotação/áudio) faz sentido tecnicamente: primeiro perfis (só muda bitrate/qualidade no `Transformer`), depois resolução/rotação (exige inserir `Effects`/`VideoCompositorSettings` no Media3, mais trabalho).

## 2. Como a compressão Android funciona hoje

`MainActivity.kt` implementa os três canais que o Flutter espera (`video_info`, `video_processing`, `video_processing_progress`) usando **AndroidX Media3 Transformer 1.10.1** — motor local, sem FFmpeg, com codec de saída H.264/AAC em MP4. Isso é uma escolha sólida e já está funcional de ponta a ponta: seleciona vídeo (SAF via `file_picker`), lê metadados (`MediaMetadataRetriever`), comprime com bitrate calculado por faixa de resolução, salva via `MediaStore` (Android 10+) ou pasta interna do app (Android < 10), e permite compartilhar/abrir/cancelar. Isso é bem mais completo que o equivalente quebrado no desktop (que tem um botão de extração de MP3 sem backend).

## 3. Bugs e riscos concretos encontrados no código Android

**a) `Uri.parse()` em caminho local pode quebrar com nomes de arquivo especiais.** Em `resolveInputUri`, quando não há URI de conteúdo (comum: `file_picker` no Android costuma devolver só `path`, um caminho de cache local, não uma `content://` URI), o código faz `Uri.parse(uriText)` diretamente sobre uma string de caminho de arquivo puro. `Uri.parse` não faz percent-encoding: qualquer nome de arquivo com `#` é interpretado como início de fragmento (trunca o caminho ali), e outros caracteres especiais podem gerar uma URI mal formada. O jeito seguro é `Uri.fromFile(File(path))` quando não há esquema, em vez de `Uri.parse` sobre o caminho cru. Isso é usado em duas frentes: `resolveInputUri` (compressão) e implicitamente no fallback de `readVideoInfo`. Vale testar com um vídeo cujo nome tenha `#`, `%` ou acentos para confirmar.

**b) `shareResult`/`openResult` falham em silêncio.** As duas funções nativas engolem qualquer exceção (`catch (_: Exception) {}`) e, mesmo assim, o handler do canal sempre chama `result.success(null)` depois. Se não houver app instalado capaz de abrir/compartilhar o vídeo, ou se a URI perder a permissão de leitura, o usuário aperta "Compartilhar"/"Abrir arquivo" e **nada acontece, sem nenhum aviso**. Vale propagar erro (`result.error(...)`) e mostrar um feedback na tela Flutter (SnackBar) nesse caso.

**c) Progresso "impreciso" prejudica a sensação de velocidade.** Quando `Transformer.getProgress` retorna `PROGRESS_STATE_UNAVAILABLE` (comum em parte dos aparelhos/vídeos), a UI mostra um indicador indeterminado sem percentual — o app parece "travado" mesmo processando normalmente. Como a premissa é fluxo extremamente rápido/responsivo, mesmo uma estimativa aproximada (tempo decorrido vs. duração do vídeo, por exemplo) passaria mais confiança do que o spinner indeterminado puro.

**d) Sem verificação prévia de espaço em disco** antes de iniciar a compressão — já reconhecido no roadmap para a Fase 5, mas continua sendo um risco real hoje para vídeos grandes (o processo pode falhar no meio, sem aviso antecipado).

**e) Bitrate fixo em degraus por resolução** (`estimateBalancedBitrate`: 1.5/3/5/8 Mbps conforme a maior dimensão) não considera a complexidade real do conteúdo (câmera parada vs. ação, ruído, etc.), então a "qualidade Balanceado" pode variar bastante entre vídeos parecidos em resolução mas diferentes em conteúdo. Aceitável para MVP, mas vale documentar como limitação conhecida (já meio reconhecido no roadmap como "equivalência com CRF 23 não direta").

## 4. Fluxo rápido — pontos fortes e a maior oportunidade perdida

**Pontos fortes já implementados:** o fluxo atual já é enxuto — selecionar vídeo, ver resumo, tocar em "Comprimir vídeo" (não tem tela intermediária nem múltiplos passos de configuração, já que as opções são fixas). Isso está alinhado com "fluxo extremamente rápido" mesmo sem querer.

**A maior oportunidade que falta:** o `AndroidManifest.xml` só declara o `intent-filter` de `MAIN`/`LAUNCHER`. Não existe um `intent-filter` para receber `ACTION_SEND` de vídeo (`video/*`). Isso significa que o usuário não pode compartilhar um vídeo direto da Galeria/WhatsApp/Câmera para o app comprimir — precisa abrir o app primeiro e navegar pelo seletor de arquivos. Para um app cuja premissa é velocidade, esse é o ganho de fluxo mais alto: "compartilhar vídeo → Preparo de Vídeos" comprime com um toque a menos e sem trocar de contexto mental (abrir app, achar botão, abrir seletor, navegar até o vídeo). Tecnicamente é barato: um `intent-filter` de `ACTION_SEND` com `video/*` no `AndroidManifest.xml`, mais tratamento do `Intent` recebido em `MainActivity`/`app.dart` para popular o `SelectedVideo` diretamente.

## 5. Design (Android já está em bom ponto, ajustes são finos)

Diferente do desktop, o Android já usa Material 3 com `ColorScheme.fromSeed`, cards com bordas suaves, chips de informação e `AnimatedSwitcher` nas transições — isso já é "moderno" por padrão do Material 3. Não é necessário redesenhar do zero. Sugestões pontuais para reforçar a sensação futurista/envolvente sem fugir do padrão Material já adotado:

- Trocar o botão "Selecionar vídeo" solitário no topo por uma área maior de destaque (tipo hero card) com o ícone de vídeo, que também aceite arrastar um arquivo quando rodando em modo desktop/Chromebook — no celular funciona como um alvo de toque maior e mais convidativo que um botão de texto.
- Usar leve gradiente (dentro da paleta seed já definida, ex. do `primaryContainer` para `tertiaryContainer`) no botão principal "Comprimir vídeo" para diferenciá-lo visualmente do resto — hoje todos os `FilledButton` têm a mesma cor sólida.
- Adicionar retorno tátil (`HapticFeedback.mediumImpact()`) ao tocar em "Comprimir vídeo" e ao concluir — reforça sensação de app rápido e responsivo em toques mobile.
- No `_ResultCard`, destacar visualmente o percentual de economia (número grande) em vez de mais uma linha de texto igual às outras — é o dado que mais importa pro usuário bater o olho.

## 6. Resumo priorizado

1. Corrigir `Uri.parse` → `Uri.fromFile` para caminhos locais (risco real de quebra silenciosa com nomes de arquivo comuns).
2. Propagar erro real em `shareResult`/`openResult` em vez de falhar silenciosamente.
3. Adicionar suporte a `ACTION_SEND` (compartilhar vídeo direto de outro app) — maior ganho de velocidade percebida.
4. Progresso com estimativa aproximada quando Media3 não fornece percentual, para não parecer travado.
5. Ajustes finos de design (hero de seleção, gradiente no botão principal, destaque do percentual de economia, haptics).
6. Seguir o roadmap já definido para Fase 3 (perfis) e Fase 4 (resolução/rotação/áudio) — está bem planejado, só falta execução.

Posso implementar qualquer um desses itens no código Kotlin/Dart — é só apontar por onde quer começar.
