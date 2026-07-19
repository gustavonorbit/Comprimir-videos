# Implementacao da Fase 2

Data: 2026-07-09

## Objetivo

Evoluir o app mobile de selecao/metadados para o primeiro fluxo de compressao Android, mantendo o desktop intacto.

## Mudancas visuais

- Tela inicial continua simples antes da selecao.
- Apos selecionar um video, tudo permanece na mesma tela.
- O card tecnico foi substituido por um resumo compacto.
- Caminhos internos, URIs longas e referencias de cache nao aparecem para o usuario.
- Conteudo limitado a largura maxima em telas amplas, adequado para tela interna de dobraveis.
- Layout continua em coluna vertical para celulares comuns e tela externa do Fold.

## Fluxo final da fase

1. Selecionar video.
2. Ver resumo: nome, tipo, tamanho, duracao, resolucao e orientacao quando util.
3. Ver opcoes do recorte funcional.
4. Ver arquivo de saida automatico.
5. Comprimir agora.
6. Ver progresso real quando o Media3 fornece percentual, ou indicador indeterminado honesto.
7. Cancelar durante o processamento.
8. Ver resultado com antes/depois/economia.
9. Compartilhar, abrir arquivo ou comprimir outro video.

## Motor Android escolhido

Motor: AndroidX Media3 Transformer 1.10.1.

Justificativa:

- E biblioteca oficial AndroidX para transformacoes de midia.
- Exporta MP4 localmente.
- Permite consultar progresso com `Transformer.getProgress`.
- Permite cancelar com `Transformer.cancel`.
- Nao depende de FFmpeg instalado.
- Nao usa FFmpegKit aposentado.
- Processamento e local, sem servidor.

Referencia tecnica consultada:

- Android Developers - Media3 Transformer Getting Started: https://developer.android.com/media/media3/transformer/getting-started

## Recorte funcional implementado

Primeira compressao Android:

- Perfil: automatico de compressao maxima aceitavel.
- Resolucao: Original.
- Rotacao: Sem rotacao.
- Audio: mantido.
- Saida: MP4.
- Codec solicitado: H.264 para video e AAC para audio.
- Original preservado.

As demais opcoes do desktop nao foram expostas como controles editaveis nesta fase porque ainda nao estao conectadas ao motor.

## Regra de saida

- Android moderno: salva em `Movies/Preparo de Videos` via MediaStore.
- Android anterior ao 10: fallback para pasta do app, evitando permissoes legadas.
- Nome: `{nome_original}_comprimido.mp4`.
- Formato final: MP4.

## Progresso

O app escuta um EventChannel nativo:

- `preparing`: preparacao.
- `processing`: compressao.
- `saving`: copia para MediaStore.
- `completed`: finalizado.
- `cancelled`: cancelamento.

Quando o Media3 retorna percentual disponivel, a UI mostra porcentagem. Quando nao retorna, a UI mostra progresso indeterminado com mensagem clara.

## Cancelamento

Durante a compressao:

- as configuracoes ficam indisponiveis;
- o botao cancelar chama `Transformer.cancel`;
- arquivo temporario e removido quando seguro;
- o original permanece intacto.

## Compartilhar e abrir

Depois do sucesso:

- Compartilhar usa `Intent.ACTION_SEND`.
- Abrir usa `Intent.ACTION_VIEW`.
- Ambos usam a URI do resultado salvo.

## Comportamento em Fold

Tela externa:

- Layout em coluna.
- Scroll vertical.
- Controles com area de toque adequada.
- Textos compactos e legiveis.

Tela interna:

- Conteudo centralizado.
- Largura maxima de 680 px para nao esticar os controles.
- Mantem leitura confortavel sem virar layout desktop.

Mudanca de tamanho:

- Estado da tela e mantido pelo `StatefulWidget` enquanto o processo Flutter nao for destruido.

## Itens ainda nao implementados

- Outros perfis manuais de compressao.
- Escolha real de resolucao.
- Rotacao.
- Remover audio.
- Extrair MP3.
- Corte.
- Blur.
- Escolha manual de destino.
- iOS.

## Preparacao para iOS

A UI depende de `VideoProcessingService`, nao de Media3 diretamente.

Futuramente o iOS deve implementar o mesmo contrato com AVFoundation, sem alterar as telas principais.

## Validacao esperada

Comandos:

```bash
flutter pub get
flutter analyze
flutter test
flutter build apk --debug
```

Teste manual:

```bash
flutter run
```

O teste manual depende de aparelho Android ou emulador funcional.
