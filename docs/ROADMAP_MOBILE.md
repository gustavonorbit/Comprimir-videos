# Roadmap Mobile

Objetivo: evoluir para Android e iOS preservando totalmente o desktop atual.

Regra base: nao criar `mobile_app/` antes da aprovacao da auditoria e deste roadmap.

## Fase 0 - Auditoria e preservacao

Objetivo:
- Mapear o desktop atual e criar contrato funcional para o mobile.

Escopo:
- Analisar Python existente.
- Documentar regras, perfis, comandos FFmpeg e riscos.
- Criar apenas documentos de auditoria.

Tarefas:
- Analisar `main.py`, `ui.py`, `compressor.py`, `utils.py`, `exemplos.py` e `requirements.txt`.
- Mapear fluxo de inicializacao.
- Mapear comandos FFmpeg/FFprobe.
- Documentar perfis reais.
- Identificar lacunas.
- Criar `RELATORIO_AUDITORIA_DESKTOP.md`.
- Criar `MAPEAMENTO_DESKTOP_MOBILE.md`.
- Criar `MATRIZ_EQUIVALENCIA_PLATAFORMAS.md`.
- Criar `ROADMAP_MOBILE.md`.

Dependencias:
- Codigo desktop atual.

Riscos:
- Estado do worktree ja contem alteracoes pendentes.
- UI possui fluxo de extracao MP3, mas backend esta ausente no `compressor.py` atual.

Criterios de aceite:
- Todos os arquivos Python relevantes analisados.
- Todas as funcoes encontradas documentadas.
- Comandos FFmpeg registrados.
- Perfis documentados com valores reais.
- Nenhuma alteracao funcional no desktop.
- Nenhuma pasta `mobile_app/` criada.

Definicao de pronto:
- Quatro documentos novos na raiz.
- Desktop preservado.
- Lacunas explicitadas como nao confirmadas.

Fora da fase:
- Criar Flutter.
- Alterar Python.
- Corrigir bug.
- Implementar compressao mobile.

## Fase 1 - Base Android

Objetivo:
- Criar base Flutter independente e validar selecao/leitura de video no Android.

Escopo:
- Criar `mobile_app/`.
- Abrir app no Android.
- Selecionar video.
- Ler tamanho, duracao, formato e resolucao.
- Exibir dados na UI.

Tarefas:
- Criar projeto Flutter em `mobile_app/`.
- Estruturar pastas:

```text
mobile_app/
├── lib/
│   ├── main.dart
│   ├── app.dart
│   ├── core/
│   ├── models/
│   ├── screens/
│   ├── services/
│   ├── widgets/
│   └── utils/
├── android/
├── ios/
├── test/
├── pubspec.yaml
└── README_MOBILE.md
```

- Criar modelos `VideoFile`, `VideoInfo`.
- Criar contrato `VideoProcessingService`.
- Implementar selecao Android.
- Implementar leitura de metadados Android.
- Criar telas iniciais.

Dependencias:
- Flutter SDK.
- Android SDK.
- Aparelho/emulador Android.
- Plugin ou platform channel para picker/metadados.

Riscos:
- Permissoes Android modernas.
- URIs sem path direto.
- Videos em nuvem/galeria que exigem copia local.

Criterios de aceite:
- App roda no Android.
- Usuario seleciona video.
- Dados basicos aparecem corretamente.
- Cancelar selecao nao quebra fluxo.
- Desktop permanece inalterado.

Definicao de pronto:
- `mobile_app/` criado.
- README mobile com comandos.
- Nenhuma compressao ainda.

Fora da fase:
- Compressao.
- iOS funcional.
- Monetizacao.
- Blur/corte.

## Fase 2 - Primeira compressao

Objetivo:
- Implementar compressao Android inicial com perfil Balanceado.

Escopo:
- Perfil Balanceado.
- Saida MP4.
- Progresso.
- Cancelamento.
- Resultado salvo.
- Original preservado.

Tarefas:
- Avaliar Media3 Transformer em POC controlada.
- Definir mapeamento inicial do Balanceado.
- Implementar `compressVideo` no Android.
- Criar tela de processamento.
- Criar tela de resultado com antes/depois.
- Implementar cancelamento.
- Limpar arquivo parcial ao cancelar/falhar.

Dependencias:
- Media3/MediaCodec/MediaMuxer.
- Storage app-specific/cache.

Riscos:
- Equivalencia com CRF 23 nao direta.
- Progresso impreciso.
- Aquecimento/bateria.
- Videos grandes.

Criterios de aceite:
- Saida `.mp4`.
- Original preservado.
- App nao trava.
- Progresso aparece.
- Cancelamento funciona.
- Erros sao amigaveis.

Definicao de pronto:
- Pelo menos 5 videos de formatos/tamanhos diferentes testados no Android.
- Resultado reproduzivel.

Fora da fase:
- Todos os perfis.
- Rotacao.
- Remocao de audio.
- Extracao MP3.
- iOS.

## Fase 3 - Perfis

Objetivo:
- Replicar no Android todos os perfis do desktop em comportamento equivalente.

Escopo:
- Alta Qualidade.
- Balanceado.
- Compressao Forte.
- Compressao Maxima.

Tarefas:
- Criar modelo `CompressionProfile`.
- Manter nomes do desktop.
- Medir tamanho/qualidade por perfil.
- Ajustar bitrate/qualidade nativa.
- Documentar diferenca para CRF.
- Criar testes manuais comparativos.

Dependencias:
- Fase 2 concluida.
- Conjunto de videos de teste.

Riscos:
- Perfis nativos nao formam reducao monotonicamente clara.
- Diferencas por aparelho.

Criterios de aceite:
- Todos os nomes aparecem na UI.
- Alta Qualidade preserva mais qualidade e tende a gerar maior arquivo.
- Compressao Maxima gera menor arquivo e qualidade inferior.
- Balanceado e padrao.

Definicao de pronto:
- Tabela de resultados Android por perfil.
- Mapeamento aprovado.

Fora da fase:
- Novas funcoes de edicao.
- iOS.

## Fase 4 - Acoes complementares

Objetivo:
- Adicionar acoes equivalentes ao desktop confirmadas e uteis no mobile.

Escopo:
- Remover audio.
- Girar video.
- Selecionar destino/salvar.
- Salvar e compartilhar.
- Extrair audio somente apos contrato desktop e POC.

Tarefas:
- Implementar remover audio omitindo track.
- Implementar rotacao 90 direita/esquerda/180.
- Implementar salvar em galeria/MediaStore.
- Implementar compartilhar arquivo.
- Avaliar extracao de audio: M4A nativo vs MP3 com alternativa.

Dependencias:
- Fases 2 e 3.
- Permissoes/storage.

Riscos:
- Rotacao por metadata pode nao ser respeitada por todos os players.
- MP3 nao e nativo simples.
- Salvar na galeria varia por versao Android.

Criterios de aceite:
- Remover audio gera video sem audio.
- Rotacao reproduz corretamente.
- Usuario consegue compartilhar.
- Usuario consegue salvar.
- Extracao de audio so entra se aprovada tecnicamente.

Definicao de pronto:
- Fluxos principais testados em aparelhos Android diferentes.

Fora da fase:
- Blur.
- Lote.
- Monetizacao.
- iOS.

## Fase 5 - Estabilidade

Objetivo:
- Tornar o MVP Android confiavel para usuarios reais.

Escopo:
- Videos grandes.
- Pouco espaco.
- Interrupcao.
- Permissoes.
- Arquivos corrompidos.
- Testes em diferentes aparelhos.

Tarefas:
- Detectar espaco disponivel antes de processar.
- Tratar permissao negada.
- Tratar arquivo corrompido.
- Tratar app em background.
- Testar videos longos e 4K.
- Testar Android em versoes diferentes.
- Criar mensagens de erro finais.

Dependencias:
- Fases anteriores.
- Matriz de dispositivos.

Riscos:
- Processamento em background limitado.
- Variacao grande de hardware.
- Avaliacoes ruins se app parecer travado.

Criterios de aceite:
- Falhas comuns mostram mensagens claras.
- App nao perde o original.
- Cancelamento nao deixa lixo visivel ao usuario.
- App nao crasha nos cenarios testados.

Definicao de pronto:
- Checklist de testes concluido.
- Bugs criticos corrigidos.

Fora da fase:
- iOS.
- Funcionalidades novas.
- Monetizacao.

## Fase 6 - Preparacao para iOS

Objetivo:
- Implementar contrato equivalente no iOS preservando telas e regras.

Escopo:
- AVFoundation para metadados/compressao.
- Permissoes.
- Salvar/compartilhar.
- Mesmos perfis em equivalencia aprovada.

Tarefas:
- Criar implementacao Swift de `VideoProcessingService`.
- Implementar leitura com AVAsset.
- Implementar compressao MP4.
- Implementar progresso/cancelamento.
- Implementar salvar em Fotos/Arquivos e Share Sheet.
- Ajustar permissoes iOS.
- Validar perfis.

Dependencias:
- Mac com Xcode.
- Dispositivo iOS real.
- Contrato Android estabilizado.

Riscos:
- AVAssetExportSession tem presets limitados.
- iOS sandbox/Photos.
- Equivalencia com Android e desktop nao exata.

Criterios de aceite:
- Mesmas telas Flutter.
- Mesmas regras de negocio.
- Original preservado.
- Saida MP4.
- Progresso/cancelamento.

Definicao de pronto:
- App rodando em iOS real.
- Funcionalidades MVP equivalentes aprovadas.

Fora da fase:
- Reescrever UI.
- Alterar desktop.
- Blur automatico.

## Recomendacao para o primeiro passo da Fase 1

Criar o projeto Flutter separado em `mobile_app/`, com apenas UI inicial, modelos e contrato `VideoProcessingService`. A primeira prova tecnica deve ser selecao de video e leitura de metadados no Android, antes de qualquer compressao.
