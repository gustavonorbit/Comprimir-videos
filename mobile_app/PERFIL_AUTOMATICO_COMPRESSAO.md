# Perfil Automatico de Compressao

Este documento registra a regra unica de compressao do aplicativo mobile.

## Referencia desktop

O desktop continua sendo a referencia conceitual e nao foi alterado. O perfil mais agressivo atual usa:

- `Compressao Maxima`
- codec de video `libx264`
- CRF `32`
- preset `fast`
- audio AAC em `128k` quando o audio e mantido
- `-movflags +faststart`
- resolucao original por padrao
- FPS original
- arquivo original preservado

## Equivalente Android

O Android usa AndroidX Media3 Transformer. Como o Media3 nao expoe CRF como o FFmpeg, o equivalente mobile usa bitrate alvo por resolucao, mantendo o fluxo simples para o usuario.

Configuracao fixa:

- estrategia: `maximumCompression`
- saida: MP4
- video: H.264
- audio: AAC mantido
- resolucao: original
- orientacao: original
- destino: `Movies/Preparo de Videos` quando permitido
- nome: `<nome>_comprimido.mp4`, com sufixo `_2`, `_3` etc. quando ja existir

Bitrate alvo:

| Video de entrada | Bitrate alvo |
|---|---:|
| ate 640 px no maior lado ou ate 480p | 700 kbps |
| ate 1280 px no maior lado ou ate 720p | 1.2 Mbps |
| ate 1920 px no maior lado ou ate 1080p | 2.2 Mbps |
| ate 2560 px no maior lado ou ate 1440p | 3.8 Mbps |
| acima disso | 5.5 Mbps |
| metadados indisponiveis | 2.5 Mbps |

O app nunca aumenta a resolucao de video pequeno. A politica de resolucao permanece `Original`.

## Decisao de produto

Nao existe seletor de qualidade na interface principal. O fluxo principal e:

1. selecionar video
2. conferir resumo compacto
3. tocar em `Comprimir agora`
4. acompanhar progresso
5. compartilhar ou abrir o resultado

As `Opções extras` ficam recolhidas e mostram apenas informacoes operacionais que realmente estao conectadas ao motor Android.

## Limitacoes

- O tamanho final pode variar conforme codec, conteudo, duracao e encoder do aparelho.
- Media3 nao usa CRF, entao a equivalencia com o desktop e aproximada.
- A compressao e com perdas, pensada para evidencias rapidas e compartilhamento, nao para arquivamento sem perda.
- iOS ainda deve implementar a mesma politica atras dos mesmos servicos da interface.
