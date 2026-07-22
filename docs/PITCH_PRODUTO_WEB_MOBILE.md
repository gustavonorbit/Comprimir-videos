# Resumo tecnico e estrategia de produto

Projeto atual: Compressor de Videos  
Direcao proposta: ferramenta web/mobile para edicao rapida, compressao inteligente e blur dinamico aplicado com poucos cliques  
Data da analise: 26 jun 2026

## 1. Tese central do produto

O projeto atual ja resolve uma dor real: reduzir tamanho de videos localmente com uma interface simples, sem exigir que o usuario entenda codecs, containers, CRF, preset, bitrate ou FFmpeg. A evolucao natural rentavel nao e virar um editor generico completo, porque esse mercado ja e ocupado por CapCut, Adobe Express, Canva, Edits, DaVinci, Premiere e similares. A oportunidade mais forte e posicionar o produto como uma ferramenta especializada em "edicao utilitaria rapida": preparar videos para envio, publicacao, privacidade, prova, rede social, WhatsApp, aulas, suporte, vendas e documentacao.

A tese de diferenciacao:

> Um editor leve para resolver tarefas urgentes de video em minutos: comprimir, converter, cortar, redimensionar e aplicar blur dinamico automatico em rostos, placas, documentos, telas, dados sensiveis ou fundos.

O foco comercial deve ser "rapidez + privacidade + facilidade", nao "editor criativo completo". O blur dinamico pode ser o recurso de assinatura porque mistura valor pratico, risco juridico, IA util e uma demonstracao visual forte para pitch.

## 2. Estado tecnico atual do projeto

O software atual e uma aplicacao desktop local escrita em Python, com interface em CustomTkinter e pipeline de midia baseado em FFmpeg/FFprobe.

Arquitetura atual:

- `main.py`: ponto de entrada. Inicializa `ctk.CTk`, instancia `VideoCompressorGUI` e entra no loop da interface.
- `ui.py`: camada de interface grafica. Gerencia selecao de arquivo, pasta de saida, presets, resolucao, rotacao, remocao de audio, progresso, cancelamento e mensagens ao usuario.
- `compressor.py`: camada de processamento. Localiza FFmpeg/FFprobe, extrai metadados do video, monta comandos FFmpeg, executa subprocessos, interpreta progresso pelo `stderr` e permite cancelar o processo.
- `utils.py`: utilitarios de tamanho, duracao, sistema, abertura de pasta e estimativa heuristica de tamanho final.
- `requirements.txt`: dependencia unica direta: `customtkinter==5.2.2`.

Capacidades implementadas:

- Entrada em multiplos formatos suportados pelo FFmpeg: MP4, MOV, MKV, AVI, WMV, FLV, WebM, M4V, MPEG, 3GP, TS, MTS e outros.
- Leitura tecnica com FFprobe: largura, altura, duracao e tamanho de arquivo.
- Saida padronizada em MP4, usando H.264 (`libx264`) e audio AAC 128 kbps.
- Perfis de compressao por CRF/preset:
  - Alta Qualidade: CRF 18, preset `slow`.
  - Balanceado: CRF 23, preset `medium`.
  - Compressao Forte: CRF 28, preset `medium`.
  - Compressao Maxima: CRF 32, preset `fast`.
- Redimensionamento proporcional com `scale=-2:altura`, preservando proporcao e garantindo dimensao par para compatibilidade com H.264.
- Rotacao manual: 90 graus direita, 90 graus esquerda e 180 graus via filtros `transpose`, `hflip` e `vflip`.
- Opcao de remover audio com `-an`.
- Otimizacao de MP4 para reproducao progressiva com `-movflags +faststart`.
- Processamento em thread separada para nao travar a UI.
- Progresso estimado com parsing de `time=HH:MM:SS.ms` emitido pelo FFmpeg.
- Cancelamento por `terminate()` e fallback para `kill()`.

Gap tecnico verificado:

- A interface possui fluxo de "EXTRAIR MP3" e chama `self.compressor.extract_audio_mp3(...)`, mas no estado atual analisado `compressor.py` nao possui esse metodo. Isso significa que a feature esta especificada na UI/documentacao, mas incompleta no backend. Para um produto, isso deve ser tratado como item imediato de estabilizacao antes de qualquer demo publica.

## 3. Valor tecnico ja existente

O principal ativo tecnico do projeto nao e a interface atual, mas sim a decisao correta de separar UI e processamento. O modulo `VideoCompressor` ja funciona como um nucleo de processamento reaproveitavel. Isso permite evoluir em tres direcoes:

- CLI/API local: transformar `compressor.py` em um pacote ou servico.
- Backend web: expor o processamento por fila de jobs.
- Mobile/web hybrid: reaproveitar a mesma logica conceitual de presets e filtros, trocando o executor por bibliotecas nativas ou WebAssembly/WebCodecs.

O segundo ativo e a escolha do FFmpeg. Ele oferece filtros de blur, crop, overlay, mascara, composicao, audio, codecs, containers e aceleracao por hardware em ambientes especificos. Isso reduz risco tecnico no MVP, porque o produto pode comecar com blur manual/semiautomatico antes de implementar IA sofisticada.

## 4. Nova visao de produto

Nome conceitual:

- BlurFast
- VideoShield
- ClipSafe
- FastBlur Studio
- PrivVideo

Posicionamento recomendado:

> O jeito mais rapido de preparar videos para compartilhar com seguranca: comprima, corte e esconda informacoes sensiveis com blur automatico.

Persona primaria:

- Professores que gravam aulas e precisam ocultar alunos, nomes, telas ou dados.
- Criadores e social media que precisam publicar rapido sem expor terceiros.
- Corretores, advogados, despachantes, suporte tecnico e pequenos negocios que gravam tela/celular e precisam ocultar dados.
- Times de atendimento, produto e QA que compartilham bugs em video com informacoes sensiveis.
- Usuarios comuns que querem enviar videos menores pelo WhatsApp/Drive/e-mail.

Job-to-be-done:

> Quando tenho um video grande ou sensivel, quero preparar uma versao segura e leve rapidamente, sem aprender edicao profissional, para poder enviar ou publicar com confianca.

## 5. Pitch curto

Hoje qualquer pessoa grava videos, mas editar, reduzir tamanho e esconder informacoes sensiveis ainda e trabalhoso. Ferramentas criativas sao grandes demais, tecnicas demais ou focadas em templates. Nosso produto resolve o lado pratico do video: ele comprime, adapta e aplica blur dinamico em rostos, placas, telas e dados privados em poucos cliques. Comecamos com um motor local baseado em FFmpeg e evoluimos para uma plataforma web/mobile com IA on-device e processamento seguro em nuvem. A promessa e simples: videos prontos para compartilhar em minutos, com privacidade e tamanho otimizado.

## 6. Por que blur dinamico e uma boa wedge feature

Blur dinamico tem alto valor percebido porque:

- Protege privacidade e reduz risco de vazamento.
- Tem resultado visual demonstravel em segundos.
- Serve para usuarios comuns e profissionais.
- Justifica monetizacao porque economiza tempo e evita problemas reais.
- Pode comecar manual e evoluir para IA sem quebrar a proposta.
- Cria um diferencial mais claro do que "mais um compressor".

Casos de uso fortes:

- Borrar rosto de criancas/alunos em video escolar.
- Borrar placa de carro em gravacoes externas.
- Borrar nomes, e-mails, telefones e documentos em gravacoes de tela.
- Borrar conversas de WhatsApp, dados bancarios ou dashboards internos.
- Borrar fundo para foco visual em video vertical.
- Borrar objeto em movimento com rastreamento automatico.

## 7. Design tecnico do blur dinamico

O blur dinamico pode ser implementado em niveis progressivos.

Nivel 1 - blur manual por area e intervalo:

- Usuario importa o video.
- Usuario pausa em um frame.
- Desenha um retangulo ou elipse sobre a area sensivel.
- Define inicio/fim na timeline.
- Sistema aplica blur naquela regiao durante o intervalo.
- Backend usa FFmpeg com filtros `crop`, `gblur` ou `boxblur`, `overlay` e `enable=between(t,start,end)`.

Vantagem: MVP rapido, previsivel e sem dependencia de IA.

Nivel 2 - blur com keyframes:

- Usuario marca a area em dois ou mais pontos da timeline.
- Sistema interpola posicao, tamanho e intensidade entre keyframes.
- Export gera filtro temporal com coordenadas variando por expressao ou segmenta o video em trechos.

Vantagem: cobre objetos em movimento mesmo sem ML.

Nivel 3 - auto blur de rostos:

- Sistema detecta faces frame a frame ou em intervalos.
- Sistema associa deteccoes ao mesmo alvo via tracking.
- Usuario escolhe "borrar todos", "borrar todos exceto este" ou "borrar selecionados".
- Sistema gera trilhas de mascara por pessoa.
- Export aplica blur por mascara com borda suavizada.

Tecnologias candidatas:

- Mobile: Google ML Kit Face Detection para Android/iOS, com deteccao e tracking em tempo real.
- Cross-platform ML: MediaPipe Face Landmarker, com suporte a Web, Android, iOS e Python.
- Backend/server: Python + OpenCV + MediaPipe/ONNX para deteccao e tracking offline.

Nivel 4 - auto blur de dados sensiveis:

- OCR detecta texto, e-mail, CPF, telefone, placas, documentos e numeros.
- Classificador decide o que e sensivel.
- Usuario revisa as caixas detectadas.
- Sistema aplica blur dinamico nas regioes confirmadas.

Essa fase aumenta muito o valor B2B, mas tambem aumenta risco de falso negativo. Deve vir depois de uma boa experiencia de revisao manual.

## 8. Pipeline tecnico proposto para export

Modelo conceitual:

```text
input video
  -> probe tecnico
  -> normalizacao de timeline
  -> plano de edicao
  -> deteccao/tracking opcional
  -> geracao de mascaras/keyframes
  -> render preview
  -> render final
  -> validacao de saida
  -> download/compartilhamento
```

Objeto de edicao recomendado:

```json
{
  "input": "video.mov",
  "output": "video_safe.mp4",
  "timeline": {
    "duration": 42.8,
    "fps": 30
  },
  "operations": [
    {
      "type": "dynamic_blur",
      "target": "manual_region",
      "shape": "rounded_rect",
      "start": 3.2,
      "end": 17.5,
      "intensity": 18,
      "feather": 8,
      "keyframes": [
        { "t": 3.2, "x": 110, "y": 220, "w": 180, "h": 90 },
        { "t": 17.5, "x": 390, "y": 240, "w": 200, "h": 92 }
      ]
    }
  ],
  "export": {
    "codec": "h264",
    "crf": 23,
    "preset": "medium",
    "resolution": "source",
    "audio": "aac_128k"
  }
}
```

Esse formato e importante porque separa a intencao do usuario do motor de renderizacao. A mesma operacao pode ser renderizada por FFmpeg no servidor, WebCodecs no navegador ou pipeline nativo no mobile.

## 9. Arquitetura web recomendada

Para web, existem duas abordagens complementares.

Opcao A - processamento no servidor:

- Frontend: Next.js/React, timeline customizada, canvas de preview, upload resumable.
- Backend: Python FastAPI ou Node.js, fila com Redis/RQ/Celery/BullMQ.
- Worker: FFmpeg instalado no servidor ou container.
- Storage: S3/R2/GCS com URLs assinadas.
- Banco: Postgres para usuarios, jobs, planos, assets e auditoria.
- Progresso: WebSocket/SSE para andamento do job.
- Billing: Stripe.

Prós:

- Mais confiavel para arquivos grandes.
- Melhor controle de codec e export.
- Permite jobs demorados, fila, historico e processamento em lote.

Contras:

- Custo de compute e storage.
- Exige cuidado com privacidade, LGPD e limpeza de arquivos.

Opcao B - processamento no navegador:

- Decodificacao/encoding com WebCodecs onde suportado.
- Preview e efeitos com Canvas/WebGL/WebGPU.
- Fallback com FFmpeg.wasm para tarefas menores.
- Arquivo pode permanecer local, reduzindo custo e aumentando privacidade.

Prós:

- Melhor argumento de privacidade.
- Menor custo por render.
- Experiencia instantanea para videos curtos.

Contras:

- Compatibilidade e performance variam muito por navegador/dispositivo.
- Arquivos longos podem consumir memoria e bateria.
- Export H.264/AAC pode ter limitacoes dependendo do ambiente.

Recomendacao:

Comecar com arquitetura hibrida. Preview e selecao de blur rodam no navegador; render final roda no servidor para confiabilidade. Depois, liberar modo local/on-device para videos curtos como diferencial premium ou privacy-first.

## 10. Arquitetura mobile recomendada

Para mobile, o caminho mais pragmático:

- UI em Flutter ou React Native se a prioridade for velocidade cross-platform.
- Pipeline nativo por plataforma para edicao/export:
  - iOS: AVFoundation/CoreImage/Vision quando fizer sentido.
  - Android: MediaCodec/Media3/ML Kit/OpenGL/Vulkan conforme necessidade.
- ML on-device para deteccao de face/objetos com ML Kit ou MediaPipe.
- Sincronizacao opcional com backend para jobs pesados.

Recomendacao de produto:

No mobile, o produto deve ser orientado a fluxo de captura/importacao rapida:

1. Importar video.
2. Escolher "borrar rostos", "borrar texto" ou "borrar area".
3. Revisar deteccoes.
4. Exportar para WhatsApp, Instagram, TikTok, Drive ou e-mail.

## 11. MVP recomendado

MVP 0 - estabilizar desktop atual:

- Implementar `extract_audio_mp3` no backend ou remover o botao temporariamente.
- Adicionar testes de compressao com video fixture pequeno.
- Validar que cancelamento limpa arquivo parcial.
- Separar mais claramente nucleo de processamento e UI.
- Criar objeto `CompressionJob`.

MVP 1 - blur manual no desktop:

- Adicionar opcao "Aplicar blur".
- Permitir selecionar area fixa.
- Permitir escolher intervalo inicio/fim.
- Aplicar `gblur`/`boxblur` em regiao com FFmpeg.
- Exportar MP4 com compressao existente.

MVP 2 - web alpha:

- Upload de video.
- Preview no navegador.
- Area de blur manual.
- Timeline simples com intervalo.
- Render final no servidor.
- Download do MP4.

MVP 3 - blur dinamico:

- Keyframes na timeline.
- Interpolacao de bounding box.
- Multiplas areas.
- Intensidade ajustavel.
- Presets: "Privacidade leve", "Privacidade forte", "Fundo suave".

MVP 4 - auto blur:

- Face detection.
- Tracking basico.
- Revisao humana antes do export.
- Borrar todos os rostos.
- Borrar rosto selecionado.

MVP 5 - monetizacao:

- Conta gratuita com limite de duracao/tamanho/marca d'agua opcional.
- Plano Pro com exports HD/4K, sem limite baixo, batch processing e auto blur.
- Plano Teams com workspace, historico, politicas de retencao e auditoria.

## 12. Modelo de receita

Freemium:

- Gratuito: compressao, corte simples, um blur manual, limite de tamanho/duracao.
- Pro mensal: blur dinamico, auto face blur, exports maiores, sem fila lenta, batch.
- Credits: videos longos ou renders em 4K consomem creditos.
- Team: gestao de usuarios, logs, storage temporario, politicas de privacidade.

Possiveis precos de referencia para testar:

- Starter: gratuito com limites.
- Pro: R$ 19 a R$ 49/mes para criadores e usuarios individuais.
- Business: R$ 99 a R$ 299/mes por workspace pequeno.
- API/Batch: cobranca por minuto processado.

Melhor wedge comercial:

- "Blur automatico de rostos e dados sensiveis" para educacao, juridico, imobiliario, suporte tecnico, saude administrativa e criadores.

## 13. Riscos tecnicos

- Performance: blur, tracking e reencode sao custosos.
- Falso negativo em privacidade: IA pode deixar rosto/texto sem borrar.
- Tamanho de upload: videos grandes exigem upload resumable e storage temporario.
- Custo de render: servidores de video podem ficar caros sem limites.
- Compatibilidade: H.264/AAC e metadados de rotacao variam por origem.
- UX de timeline: se ficar parecida com editor profissional, perde a proposta de simplicidade.
- LGPD: processar videos sensiveis exige politicas claras de retencao, exclusao e consentimento.

Mitigacoes:

- Sempre exigir revisao visual antes do export quando a deteccao for automatica.
- Mostrar aviso de que auto blur auxilia, mas o usuario deve revisar.
- Apagar arquivos automaticamente apos janela curta.
- Usar URLs assinadas e storage criptografado.
- Separar plano gratuito de plano pago por custo computacional.
- Criar benchmark de tempo por minuto de video.

## 14. Diferenciacao contra players grandes

CapCut e Adobe Express comunicam edicao facil, templates, IA, social media, captions e ferramentas amplas. O espaco livre esta em uma ferramenta mais vertical, rapida e orientada a privacidade operacional.

Nao competir em:

- Biblioteca gigante de templates.
- Rede social interna.
- Editor multipista profissional.
- Geracao de video por IA como produto principal.

Competir em:

- Velocidade para resolver tarefa especifica.
- Blur dinamico muito simples.
- Privacidade clara.
- Compressao integrada.
- Export direto para canais comuns.
- Experiencia "sem curva de aprendizado".

## 15. Arquitetura de dados para produto

Entidades principais:

- `User`: conta, plano, limites.
- `Workspace`: contexto de equipe.
- `MediaAsset`: arquivo original, derivados, metadados.
- `EditProject`: timeline, operacoes, versoes.
- `RenderJob`: status, progresso, custo estimado, logs.
- `DetectionTrack`: trilhas de face/texto/objeto.
- `BlurRegion`: regioes manuais ou automaticas.
- `ExportPreset`: formato, resolucao, codec, bitrate/CRF.

Estados de job:

- `uploaded`
- `analyzing`
- `ready_for_review`
- `queued`
- `rendering`
- `completed`
- `failed`
- `expired`
- `deleted`

## 16. Stack recomendada para primeira versao web

Frontend:

- Next.js ou Vite + React.
- Canvas para preview e desenho de regioes.
- Zustand ou Redux Toolkit para estado do editor.
- Tailwind ou design system proprio.
- Video.js ou player HTML5 customizado.

Backend:

- FastAPI em Python para proximidade com o codigo atual.
- Celery/RQ + Redis para fila.
- FFmpeg em workers Docker.
- Postgres para dados.
- S3/R2 para storage temporario.
- WebSocket/SSE para progresso.

ML:

- Fase inicial: sem ML, blur manual.
- Fase auto face: MediaPipe/ML Kit/OpenCV.
- Fase dados sensiveis: OCR + regras + revisao humana.

Infra:

- Docker.
- Workers separados por tamanho de video.
- Retencao automatica: 24h gratuito, configuravel no pago.
- Observabilidade: logs por job, tempo por minuto, falhas por codec.

## 17. Roadmap de 90 dias

Dias 1-15:

- Corrigir gap do MP3.
- Criar testes minimos.
- Refatorar nucleo de processamento para jobs.
- Implementar blur manual fixo no desktop.

Dias 16-30:

- Adicionar intervalo temporal e intensidade.
- Export com multiplas regioes simples.
- Criar demo local forte para pitch.
- Medir performance em videos reais.

Dias 31-60:

- Criar web alpha com upload, preview, area de blur e render no servidor.
- Adicionar autenticacao basica.
- Adicionar fila e progresso.
- Deploy fechado para teste.

Dias 61-90:

- Implementar keyframes.
- Implementar auto face blur beta.
- Adicionar pricing wall.
- Fazer testes com 10-30 usuarios reais.
- Medir disposicao de pagamento.

## 18. Metricas de validacao

Produto:

- Tempo ate primeiro export concluido.
- Percentual de usuarios que exportam no primeiro uso.
- Minutos de video processados por usuario.
- Percentual de usuarios que usam blur.
- Quantidade media de regioes borradas por video.
- Taxa de retrabalho apos preview.

Negocio:

- Conversao free para Pro.
- Custo medio por minuto renderizado.
- Receita por minuto processado.
- Churn apos primeiro mes.
- CAC por nicho.
- Suporte por 100 exports.

Qualidade tecnica:

- Taxa de falha por formato de entrada.
- Tempo de render por minuto de video.
- Precisao subjetiva do tracking.
- Incidencia de falso negativo em auto blur.
- Tamanho final medio por preset.

## 19. Demo ideal para pitch

Roteiro de demonstracao:

1. Importar um video comum com rosto, placa ou dado sensivel.
2. Mostrar tamanho original e duracao.
3. Clicar em "Auto blur".
4. Sistema detecta areas sensiveis.
5. Usuario revisa e ajusta uma area.
6. Escolhe "Comprimir para WhatsApp" ou "Exportar HD".
7. Export final mostra reducao de tamanho e comparacao antes/depois.

Mensagem principal:

> O usuario nao editou um video; ele resolveu um problema de compartilhamento seguro.

## 20. Referencias tecnicas e de mercado consultadas

- FFmpeg Filters Documentation: https://ffmpeg.org/ffmpeg-filters.html
- MDN WebCodecs API: https://developer.mozilla.org/en-US/docs/Web/API/WebCodecs_API
- Google ML Kit Face Detection: https://developers.google.com/ml-kit/vision/face-detection
- MediaPipe Face Landmarker: https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker
- CapCut pagina principal e ferramentas de video/blur: https://www.capcut.com/ e https://www.capcut.com/tools/blur-video-background
- Adobe Express Online Video Editor: https://www.adobe.com/express/feature/video/editor
