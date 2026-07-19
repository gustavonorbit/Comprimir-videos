# Preparo de Videos Mobile

Aplicativo Flutter independente para Android e futuramente iOS.

O app preserva o desktop Python e evolui em uma base mobile separada.

## Estado atual

- Fase 1: selecao de video e leitura de metadados.
- Fase 2: interface simplificada e primeira compressao Android funcional com perfil automatico de compressao maxima aceitavel.
- Etapa de estabilizacao Android: resolucao de URI centralizada e segura, tratamento real de erro ao abrir/compartilhar (sem falha silenciosa), recebimento de video via "Compartilhar" (`ACTION_SEND`), progresso honesto (indeterminado real quando o Media3 nao informa percentual, com tempo decorrido) e pequenos refinamentos de haptics/destaque de resultado. Detalhes em `ESTABILIZACAO_ANDROID.md`.
- Pesquisa experimental (debug-only, fora do pipeline de producao): ferramenta interna de benchmark comparando o VBR atual com 3 configuracoes de modo de qualidade constante (CQ). O botao "Benchmark CQ (debug)" so existe em build debug. Detalhes, tabela de resultados e criterio de decisao em `BENCHMARK_CQ_FOLD6.md`.

Nao ha FFmpeg, FFmpegKit, extracao de audio, corte ou blur.

## Pre-requisitos

- Flutter 3.41.4 ou compativel.
- Dart 3.11.1 ou compativel.
- Android SDK configurado.
- Android Emulator ou aparelho fisico.

Verifique com:

```bash
flutter --version
flutter doctor
```

## Dependencias utilizadas

| Dependencia | Uso | Justificativa |
|---|---|---|
| `file_picker` | Selecionar videos | Permite abrir o seletor de arquivos/midia sem pedir acesso irrestrito ao armazenamento. Trabalha com arquivos do sistema e evita `MANAGE_EXTERNAL_STORAGE`. |
| `mime` | Complementar deteccao de tipo | Ajuda a inferir MIME type pelo nome quando o Android nao retornar o tipo. |
| `androidx.media3:media3-transformer` | Compressao Android nativa | Motor oficial AndroidX para exportar MP4 localmente, consultar progresso e cancelar exportacao. |
| `androidx.media3:media3-effect` | Suporte ao Transformer | Dependencia recomendada pela documentacao oficial do Media3 Transformer. |
| `androidx.media3:media3-common` | Tipos comuns Media3 | Define `MediaItem`, MIME types e classes compartilhadas do Media3. |

Nao foram adicionadas dependencias de FFmpeg, FFmpegKit ou processamento em servidor.

## Android

Versao minima configurada:

```text
minSdk 23
```

O app usa:

- seletor de arquivos/midia via `file_picker`;
- `content://` URI quando disponivel;
- resolucao de URI centralizada em `InputUriResolver` (content/file usados como estao; caminho local bruto vira `Uri.fromFile`, nunca `Uri.parse` direto, para nao quebrar com espacos, acentos, `#`, `%` etc.);
- `MediaMetadataRetriever` por MethodChannel para ler duracao, largura, altura e rotacao;
- `ContentResolver` para nome, tamanho e MIME type quando disponivel;
- AndroidX Media3 Transformer para a compressao local automatica;
- MediaStore para salvar o resultado em `Movies/Preparo de Videos` no Android moderno;
- `FileProvider` para expor com seguranca o resultado salvo na pasta do app (fallback pre-Android 10), em vez de uma URI `file://` crua;
- `intent-filter` de `ACTION_SEND` (`video/*`) para receber video compartilhado de outro app.

Permissoes:

- nenhuma permissao de armazenamento amplo foi adicionada;
- `MANAGE_EXTERNAL_STORAGE` nao e usada;
- permissoes legadas de armazenamento nao foram adicionadas;
- `FileProvider` concede apenas leitura temporaria (`FLAG_GRANT_READ_URI_PERMISSION`) do arquivo especifico compartilhado/aberto.

## iOS futuro

A pasta `ios/` gerada pelo Flutter foi mantida.

Ainda nao ha implementacao especifica de iOS nesta fase. A arquitetura evita colocar codigo Android dentro das telas. A futura implementacao deve usar Photos framework, document picker e AVFoundation atras dos mesmos servicos usados pela interface.

## Estrutura criada

```text
mobile_app/
├── lib/
│   ├── main.dart
│   ├── app.dart
│   ├── core/
│   │   ├── errors/
│   │   │   └── app_error.dart
│   │   └── utils/
│   │       └── formatters.dart
│   ├── models/
│   │   └── selected_video.dart
│   ├── screens/
│   │   └── home_screen.dart
│   ├── services/
│   │   ├── media_picker_service.dart
│   │   ├── shared_video_service.dart
│   │   └── video_info_service.dart
│   └── widgets/
│       └── selected_video_card.dart
├── android/
├── ios/
├── test/
├── pubspec.yaml
├── README_MOBILE.md
└── ESTABILIZACAO_ANDROID.md
```

## Como instalar dependencias

```bash
cd mobile_app
flutter pub get
```

## Como executar no Android Emulator

1. Abra um emulador pelo Android Studio ou pela linha de comando.
2. Confirme que ele aparece:

```bash
flutter devices
```

3. Rode:

```bash
flutter run
```

## Como executar em aparelho Android fisico

1. Ative o modo desenvolvedor no aparelho.
2. Ative depuracao USB.
3. Conecte o aparelho.
4. Confirme que ele aparece:

```bash
flutter devices
```

5. Rode:

```bash
flutter run
```

## Como executar testes

```bash
cd mobile_app
flutter test
```

## Validacao recomendada

```bash
cd mobile_app
flutter pub get
flutter analyze
flutter test
flutter build apk --debug
```

Se houver emulador ou aparelho disponivel:

```bash
flutter run
```

## Limitacoes atuais

- Apenas o perfil automatico de compressao maxima aceitavel esta funcional na compressao Android.
- A compressao usa MP4, resolucao original, orientacao original e audio mantido.
- O app nao exibe seletor de qualidade; a configuracao e calculada automaticamente conforme a resolucao do video.
- As demais opcoes do desktop ainda nao aparecem como controles para evitar configuracoes sem efeito.
- Nao extrai MP3.
- Nao implementa corte.
- Nao implementa blur.
- Nao usa FFmpeg.
- Nao usa FFmpegKit.
- Metadados dependem do que o Android consegue ler do arquivo selecionado.
- Arquivos remotos ou em nuvem podem depender do provedor do arquivo.
- Em Android anterior ao 10, o destino pode cair para pasta do app por causa das limitacoes de escrita publica sem permissoes legadas.

## Fora do escopo desta fase

- Motores de compressao alem do recorte Media3 automatico.
- AVFoundation.
- FFmpeg/FFmpegKit.
- Monetizacao.
- Perfis adicionais de compressao.
- Historico.
- Relatorios.

## Observacao sobre copia temporaria

O app nao copia videos manualmente nesta fase. A selecao e feita via `file_picker` com `withData: false`, evitando carregar o arquivo inteiro em memoria. Dependendo do provedor de arquivos e da plataforma, o plugin pode disponibilizar um caminho local/cache para acesso seguro. Quando isso ocorrer, o app apenas registra esse caminho como `localPath`; nao cria copia adicional propria.

## Fluxo atual

1. Selecionar video pelo seletor **ou** compartilhar um video de outro app (Galeria, WhatsApp etc.) direto para "Preparo de Videos".
2. Ver resumo compacto. A compressao nunca comeca sozinha, mesmo quando o video chega por compartilhamento.
3. Abrir `Opções extras` apenas se quiser conferir formato, destino e politica aplicada.
4. Tocar em `Comprimir agora`.
5. Acompanhar progresso real quando disponivel pelo Media3; quando indisponivel, ver indicador indeterminado com tempo decorrido (nao e uma estimativa de tempo restante).
6. Cancelar se necessario.
7. Ver resultado com tamanho original, final e economia (percentual em destaque).
8. Compartilhar ou abrir o arquivo. Se nao houver app compativel ou a acao falhar, uma mensagem clara aparece em vez de nada acontecer.

## Proximo passo

A proxima etapa deve expandir os controles gradualmente: remover audio, corte, blur e rotacao. Cada controle so deve aparecer quando estiver conectado ao motor Android.
