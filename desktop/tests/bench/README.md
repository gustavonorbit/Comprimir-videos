# Benchmark do pipeline de compressão

Mede o pipeline **real** de compressão do app desktop — o mesmo
`VideoCompressor.compress_video` que o botão de exportar chama — sobre vídeos
**reais** gerados com ffmpeg. Não há mock em lugar nenhum: todo número no JSON
saiu de um processo ffmpeg medido rodando sobre um arquivo em disco.

O objetivo é ter uma linha de base **antes** de otimizar. Sem ela não dá para
provar que uma mudança acelerou nada, e — mais importante — não dá para
perceber que ela pagou essa velocidade com qualidade de imagem.

## Como rodar

```bash
# Smoke test: fontes curtas, VMAF subamostrado. Medido: 6,8 e 7,8 min do zero
# (8 núcleos, Intel), incluindo gerar as fontes; ~7 min reaproveitando-as.
python desktop/tests/bench/run_bench.py --quick

# Baseline completo. É o que se commita.
python desktop/tests/bench/run_bench.py --label baseline

# Recortes durante investigação
python desktop/tests/bench/run_bench.py --sources uhd_4k30 --profiles "Compressão Máxima"
python desktop/tests/bench/run_bench.py --quick --no-vmaf     # só tempo/tamanho/memória

# Mede com encoder de hardware (o padrão é software, ver abaixo)
python desktop/tests/bench/run_bench.py --quick --hardware
```

O run completo é **caro**, e a maior parte disso é gerar as fontes: numa máquina
Intel de 8 núcleos, gerar os ~13 min de vídeo de origem levou **2h20**, contra
poucos minutos por combinação depois. Essa parte é paga uma vez só — as fontes
ficam cacheadas em `media/` e o próximo run as reaproveita. Reserve a máquina.

Não precisa instalar nada além dos binários: o script usa o ffmpeg/ffprobe de
`desktop/bin` (o mesmo que vai no app) através da mesma lógica de descoberta do
compressor. Num clone novo eles não existem ainda — rode
`python desktop/tools/fetch_ffmpeg.py` antes. `psutil` é usado se estiver
disponível, mas não é necessário.

O JSON vai para `results/<timestamp>_<Sistema>-<arquitetura>.json`.

### Comparar dois runs

```bash
python desktop/tests/bench/compare_bench.py \
    desktop/tests/bench/results/BASELINE.json \
    desktop/tests/bench/results/NOVO.json
```

Imprime a tabela de delta e sai com **código 1** se alguma regressão passar do
limiar, então serve direto como check de CI. Limiares padrão (ajustáveis com
`--time-pct`, `--size-pct`, `--vmaf-drop`, `--low-drop`):

| Métrica | Vira regressão em |
|---|---|
| Wall time | mais de **+5%** |
| Tamanho de saída | mais de **+2%** |
| VMAF médio | queda de mais de **0,5** ponto |
| VMAF 1% low | queda de mais de **1,0** ponto |

+5% no tempo fica acima do ruído de repetição na mesma máquina (~2-3%).

## Os vídeos de teste

Gerados por `bench_sources.py` com lavfi, determinísticos (mesmo spec ⇒ mesmos
pixels, em qualquer máquina) e cacheados em `media/` — o nome do arquivo carrega
o hash do spec, então mudar a receita gera um arquivo novo em vez de reaproveitar
um vídeo velho em silêncio. `media/` não é versionado; `--regen-sources` força
regeneração.

| Fonte | O que é | Por que está aqui |
|---|---|---|
| `screen_1080p30` | 1080p30, 10 min, gravação de tela, baixo movimento e muito texto | Caso mais comum de QA. Bordas duras sobre fundo chapado: regressão aparece primeiro no **tamanho** |
| `motion_1080p60` | 1080p60, 2 min, alto movimento | Caso caro em **CPU** |
| `uhd_4k30` | 4K30, 1 min | Caso caro em **memória** (pico medido: 2,7 GB) |
| `portrait_rotado` | 1080p30, 2 min, rotação 90° no display matrix | Retrato de celular. Exercita a auto-rotação, o caminho mais frágil do pipeline (ver `tests/test_rotation_metadata.py`) |

Cada fonte tem trilha de áudio real, porque o pipeline reencoda áudio em AAC
128k e isso entra no tamanho de saída.

**Sobre "muito texto":** o texto da gravação de tela é desenhado com `drawbox`,
não com `drawtext`. Isso nasceu de uma limitação: o ffmpeg embutido do macOS na
época (Homebrew 8.1) era compilado **sem** `--enable-libfreetype`, então
`drawtext` não existia nele — só no binário do Windows. Usar `drawtext` faria os
vídeos de origem serem diferentes entre os dois sistemas, que é exatamente o tipo
de incomparabilidade que este benchmark existe para evitar.

Os binários atuais (ver `desktop/tools/README.md`) já têm libfreetype nos dois
sistemas, então `drawtext` seria possível hoje. Continua com `drawbox` de
propósito: trocar mudaria os pixels das fontes, o que muda o `fingerprint` e
invalida todo baseline já medido. Para o x264 o que importa é o que a fonte
produz — bordas de alto contraste sobre fundo chapado, com atualização local por
quadro — e isso o `drawbox` reproduz.

Cada fonte roda contra os 4 perfis de `COMPRESSION_PROFILES`
(Alta Qualidade / Balanceado / Compressão Forte / Compressão Máxima),
com `resolution=0` e sem rotação manual: mede-se a compressão pura, sem o
caminho de edição/segmentos.

## Software vs hardware

Por padrão o bench roda em **software** (libx264), que é o caminho garantido em
qualquer máquina. Com `--hardware` ele detecta os encoders da máquina
(`encoder_caps`) e mede o que o `encoder_policy` escolheria. Cada resultado
grava o encoder que **realmente** rodou (`encoder`, `encoder_is_hardware`,
`encoder_args`) — inclusive quando houve fallback de hardware para software, que
de outra forma passaria por ganho legítimo.

### O que a primeira medição mostrou (2026-08-18, Mac Intel, VideoToolbox)

Naquela máquina o VideoToolbox só aceita **bitrate alvo**, não qualidade
constante. Contra o libx264, nos 12 pares que usaram hardware:

| Métrica | Delta |
|---|---|
| Tempo | **-45% a -70%** (2x a 3x mais rápido) |
| Pico de RSS | **-80%** |
| Tamanho do arquivo | **+13% a +288%** |
| VMAF médio | de +4,9 a **-21,5** pontos |

O pior caso de tamanho (`screen_1080p30 / Compressão Máxima`) saiu **3,9x
maior**; o pior de qualidade (`motion_1080p60 / Compressão Máxima`) caiu de
VMAF 83,3 para 61,8. Bitrate alvo gasta os mesmos bits numa tela parada e numa
cena de ação — o CRF não. Por isso o `encoder_policy` **recusa** hardware que
só ofereça bitrate (ver `ALLOW_BITRATE_HARDWARE`), e por isso este run está
versionado: é a evidência da decisão.

Modos de **qualidade constante** (`-q:v` em Apple Silicon, `-cq` no NVENC,
`-global_quality` no QSV) continuam habilitados e **ainda não foram medidos** —
falta hardware. Medi-los é pré-requisito para confiar neles.

## Como ler o resultado

```jsonc
{
  "schema_version": 1,
  "run":         { "quick": false, "vmaf_n_subsample": 1, "total_elapsed_s": ... },
  "environment": { "platform": {...}, "cpu_logical_cores": 8, "ffmpeg": {...} },
  "sources":     [ { "spec": {...}, "fingerprint": "...", "media": {...} } ],
  "results":     [ { ...uma entrada por (fonte × perfil)... } ]
}
```

Cada item de `results`:

| Campo | Significado |
|---|---|
| `wall_time_s` | Tempo de parede do `compress_video` inteiro (inclui abrir e muxar, não só o laço do x264) — é o tempo que o usuário sente |
| `output_bytes` / `input_bytes` | Tamanhos medidos em disco |
| `compression_ratio_pct` | Quanto do original sumiu, `(entrada-saída)/entrada*100`. Mesma convenção de `utils.estimate_output_size` |
| `size_ratio` | `saída/entrada` |
| `encode_fps_avg` | Frames da saída ÷ `wall_time_s` |
| `rss.peak_rss_bytes` | Pico de memória residente do processo ffmpeg |
| `vmaf.mean` | VMAF médio (modelo `vmaf_v0.6.1`) |
| `vmaf.low_1pct` | Média do **pior 1%** dos frames |
| `vmaf.psnr_y_mean` | PSNR do canal Y |

**Leia `vmaf.low_1pct` junto com `vmaf.mean`.** A média esconde degradação
localizada: um vídeo pode ter VMAF médio 95 e mesmo assim ter uma cena em que a
compressão visivelmente quebra. É essa cauda que uma otimização de velocidade
costuma piorar primeiro. Como referência grosseira de VMAF: ~95+ é
indistinguível do original em uso normal, ~90 é bom, abaixo de ~80 a perda é
percebida.

### O que torna dois JSONs comparáveis

Só compare runs com o **mesmo ambiente**. O `compare_bench.py` avisa (mas não
impede) quando divergem: sistema, arquitetura (`platform.machine()`), número de
núcleos lógicos, versão do ffmpeg, se o binário é o embutido ou o do sistema,
modo `--quick` e `n_subsample` do VMAF. Também avisa se o `fingerprint` de uma
fonte mudou — aí os vídeos não são os mesmos e nenhum número é comparável.

Em particular, **`--quick` não é comparável com o run completo**: no modo quick
as fontes são mais curtas e codificadas em `veryfast`, o que deixa a referência
menos limpa e empurra todos os VMAF do run para cima.

## Ressalvas de medição

- **Pico de RSS** é exato no Windows (`PeakWorkingSetSize`, contabilizado pelo
  kernel). Em macOS/Linux é o máximo de amostras a cada 250 ms, então um pico
  mais curto que isso pode passar despercebido — o JSON registra `rss.method` e
  `rss.samples` para o número poder ser julgado.
- O bench mede o pipeline **sem** blur temporal nem segmentos de timeline. Esses
  caminhos (`_build_segmented_command`) são bem mais caros e merecem um baseline
  próprio.
- Rode com a máquina ociosa. Térmica e outros processos afetam wall time bem
  mais que a maioria das otimizações que se quer medir.
- **Não compare `run.total_elapsed_s` entre dois runs.** Ele inclui gerar as
  fontes e calcular VMAF, então um run que gerou as fontes e outro que as
  reaproveitou diferem por minutos sem que a compressão tenha mudado nada. O
  número comparável é a soma dos `wall_time_s` — que é o que o
  `compare_bench.py` usa.
- O ruído por combinação é maior do que os ~2-3% agregados nas combinações
  **curtas**: três repetições seguidas de `screen_1080p30 / Compressão Forte`
  (~10 s) variaram 6% entre si, com a máquina ociosa e o mesmo binário. Uma
  única combinação acima do limiar de +5% não é regressão — repita antes de
  acreditar.
