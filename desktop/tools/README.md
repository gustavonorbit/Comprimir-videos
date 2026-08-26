# Binários embutidos de FFmpeg

O app embute FFmpeg e FFprobe em `desktop/bin/`. Eles **não são versionados no
git** — são baixados e conferidos por `fetch_ffmpeg.py`.

```bash
python desktop/tools/fetch_ffmpeg.py            # baixa para a plataforma atual
python desktop/tools/fetch_ffmpeg.py --check    # só valida o que já está lá
python desktop/tools/fetch_ffmpeg.py --force    # rebaixa por cima
python desktop/tools/fetch_ffmpeg.py --update   # re-fixa o manifesto no build mais novo
```

`build_macos.sh` já chama o script sozinho; num clone novo, rode-o uma vez antes
de abrir o app pelo `main.py`.

## Por que não são versionados

O build estático universal do macOS tem ~154 MB por binário. O GitHub **rejeita**
qualquer arquivo acima de 100 MB, então versioná-los é impossível sem Git LFS.
O que fica no git é o `ffmpeg_manifest.json`: as URLs exatas e os SHA-256
esperados. É ele que torna o download reproduzível e auditável — o script se
recusa a instalar qualquer arquivo cujo hash não bata com o fixado ali.

## Qual bug isso corrige

O binário macOS que vinha versionado era o do Homebrew Intel
(`/usr/local/Cellar/ffmpeg/8.1_1`), **linkado dinamicamente** contra ~17 dylibs
em `/usr/local/opt/`. Dois defeitos, ambos invisíveis na máquina de quem buildou:

| Defeito | Sintoma para o usuário |
|---|---|
| Só tem `x86_64` | Em Apple Silicon roda sob Rosetta 2, mais lento, sem aviso nenhum |
| Linkado dinamicamente | Em Mac sem aquelas fórmulas do Homebrew, morre com erro de dyld — "falha ao comprimir" |

`desktop/tests/test_bundled_ffmpeg.py` falha se qualquer um dos dois voltar.

## Fontes

| Plataforma | Fonte | Por quê |
|---|---|---|
| macOS | [ffmpeg.martin-riedl.de](https://ffmpeg.martin-riedl.de/) | Única fonte pública com builds estáticos das **duas** arquiteturas macOS na mesma configuração de compilação — requisito para juntá-las num `universal2` coerente com `lipo`. Publica `.sha256` e mantém URLs versionadas por build |
| Windows | [BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds) | Build estático de referência do ecossistema. Tags datadas (`autobuild-...`) têm URL de asset estável, então dá para fixar o hash |

evermeet.cx, a fonte macOS mais conhecida, publica **só x86_64** — não serve para
universal. Homebrew é dinâmico por definição, que é exatamente o bug de origem.

O binário macOS é montado localmente: baixa-se o `arm64` e o `x86_64` e o script
os junta com `lipo -create`.

## O que é validado

`--check` (e o teste equivalente) reprova o binário se:

- não existir, não for arquivo comum, ou não for executável;
- **(macOS)** `otool -L` mostrar dependência fora de `/usr/lib` e `/System`;
- **(macOS)** `lipo -archs` não incluir a arquitetura da máquina atual;
- `ffmpeg -version` reportar menos que 8.0;
- faltar um encoder de que o código depende (`libx264`, `aac`), os de
  VideoToolbox no macOS, ou o filtro `libvmaf` que o benchmark usa.

## Versões fixadas hoje

| Plataforma | FFmpeg | Observação |
|---|---|---|
| macOS | 9.0 | universal2 (`arm64` + `x86_64`), estático, com VideoToolbox, libvmaf, libsvtav1 e libfreetype |
| Windows | 8.1.2 | estático, com nvenc/amf/qsv |

As versões divergem porque cada fonte publica trilhos diferentes. Não é um
problema em runtime — cada plataforma roda a sua —, mas vale saber ao comparar
resultados de benchmark **entre** sistemas (o `compare_bench.py` avisa quando a
versão do ffmpeg difere entre dois JSONs). Para alinhar, é só ajustar
`asset_re`/fonte em `fetch_ffmpeg.py` e rodar `--update`.

## Licença

Os dois builds são `--enable-gpl --enable-version3`, ou seja **GPL-3.0**. É a
mesma licença já declarada pelo app (`NSHumanReadableCopyright` em `build.spec`),
então distribuir o binário junto é coerente — mas isso obriga a oferecer o código
fonte correspondente do FFmpeg a quem receber o app.
