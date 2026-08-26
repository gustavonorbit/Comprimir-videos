"""
Geração dos vídeos de teste do benchmark.

Os quatro vídeos correspondem ao que um QA realmente grava e cobrem os
regimes de codificação que se comportam de forma diferente sob x264:

  screen_1080p30    conteúdo de tela: fundo chapado, bordas duras, quase
                    estático — o caso em que o encoder gasta pouco e uma
                    regressão aparece primeiro no tamanho, não no tempo.
  motion_1080p60    alto movimento a 60 fps: o caso caro em tempo de CPU.
  uhd_4k30          4K: o caso caro em memória e banda de decodificação.
  portrait_rotado   1080p30 com rotação de display matrix, como celular
                    grava — exercita o caminho de auto-rotação, que é o
                    mais frágil do pipeline (ver tests/test_rotation_metadata.py).

Todos são determinísticos: mesmo spec, mesmos pixels, em qualquer máquina.
Isso é o que permite comparar dois JSONs de plataformas diferentes.

Sobre texto na gravação de tela: o enunciado original pedia ``drawtext``,
mas o ffmpeg embutido do macOS (``desktop/bin/ffmpeg``, Homebrew 8.1) é
compilado SEM ``--enable-libfreetype``, então ``drawtext`` não existe nele
(o binário do Windows tem). Usar drawtext deixaria os vídeos de origem
diferentes entre os dois sistemas e os resultados incomparáveis, que é
exatamente o que o benchmark existe para evitar. As linhas de texto são
então desenhadas com ``drawbox``, disponível nos dois binários: para o
x264 o que importa é o que a fonte produz — bordas de alto contraste sobre
fundo chapado com atualização local — e isso o drawbox reproduz.
"""

import hashlib
import json
import random
from dataclasses import dataclass, asdict
from pathlib import Path

from bench_lib import probe_media, run_command


@dataclass
class SourceSpec:
    """Receita determinística de um vídeo de teste."""
    name: str
    description: str
    width: int
    height: int
    fps: int
    duration_s: float
    kind: str                      # screen | motion | uhd | portrait
    source_crf: int = 16           # qualidade da própria fonte (referência do VMAF)
    source_preset: str = 'medium'
    rotate_metadata: int = 0       # graus gravados no display matrix do container
    seed: int = 20260815

    def fingerprint(self) -> str:
        """Hash da receita inteira: identifica o arquivo em cache e detecta mudança.

        Entra no hash não só os campos do spec, mas o filtergraph e as entradas
        lavfi já materializados. É o que fecha o buraco óbvio de um cache por
        spec: editar o código de ``_screen_filter`` muda os pixels sem mudar
        nenhum campo, e um hash só dos campos reaproveitaria em silêncio o
        vídeo antigo — fazendo o run parecer comparável com um baseline que na
        verdade mediu outro conteúdo.
        """
        payload = json.dumps({
            'spec': asdict(self),
            'video_input': _lavfi_video_input(self),
            'video_filter': _video_filter(self),
            'audio_input': _audio_input(self),
        }, sort_keys=True).encode('utf-8')
        return hashlib.sha256(payload).hexdigest()[:16]

    def filename(self) -> str:
        return f"{self.name}_{self.fingerprint()}.mp4"


# Durações do bench completo. O modo --quick as encurta (ver quick_variant).
FULL_SOURCES = [
    SourceSpec(
        name='screen_1080p30',
        description='Gravação de tela sintética 1080p30, baixo movimento, muito texto',
        width=1920, height=1080, fps=30, duration_s=600.0, kind='screen',
    ),
    SourceSpec(
        name='motion_1080p60',
        description='1080p60 de alto movimento',
        width=1920, height=1080, fps=60, duration_s=120.0, kind='motion',
    ),
    SourceSpec(
        name='uhd_4k30',
        description='4K30 de conteúdo detalhado',
        width=3840, height=2160, fps=30, duration_s=60.0, kind='uhd',
    ),
    SourceSpec(
        name='portrait_rotado',
        description='1080p30 retrato de celular (rotação 90 no display matrix)',
        width=1920, height=1080, fps=30, duration_s=120.0, kind='portrait',
        rotate_metadata=90,
    ),
]

# Durações do modo --quick, dimensionadas para o run inteiro a partir do zero
# (geração das 4 fontes + 16 compressões + 16 medições de VMAF) caber no
# orçamento de 10 minutos numa máquina de 8 núcleos.
QUICK_DURATIONS = {
    'screen_1080p30': 24.0,
    'motion_1080p60': 15.0,
    'uhd_4k30': 6.0,
    'portrait_rotado': 15.0,
}

# No modo --quick a própria fonte é codificada em 'veryfast': gerar as 4 fontes
# em 'medium' custava ~3 min dos 10 disponíveis. A referência fica um pouco
# menos limpa, o que empurra todos os VMAF do run para cima — por isso um JSON
# de --quick só pode ser comparado com outro de --quick, nunca com o baseline
# completo (o compare_bench avisa quando os modos diferem).
QUICK_SOURCE_PRESET = 'veryfast'


def get_sources(quick: bool) -> list:
    """Lista de specs do modo pedido."""
    if not quick:
        return list(FULL_SOURCES)
    return [
        SourceSpec(**{
            **asdict(spec),
            'duration_s': QUICK_DURATIONS[spec.name],
            'source_preset': QUICK_SOURCE_PRESET,
        })
        for spec in FULL_SOURCES
    ]


# --------------------------------------------------------------------------
# Filtergraphs por tipo de conteúdo
# --------------------------------------------------------------------------

def _screen_filter(spec: SourceSpec) -> str:
    """Página de 'documento': barra de título, sidebar e linhas de texto.

    As linhas aparecem progressivamente ao longo da duração (como alguém
    rolando/digitando), o que dá o padrão real de uma gravação de tela:
    quadros quase idênticos com uma região pequena mudando por vez.
    """
    rnd = random.Random(spec.seed)
    width, height = spec.width, spec.height
    scale = width / 1920.0

    def px(value: float) -> int:
        return max(1, int(round(value * scale)))

    parts = [
        f"drawbox=x=0:y=0:w={width}:h={px(64)}:color=0x2B2B2B@1.0:t=fill",
        f"drawbox=x=0:y={px(64)}:w={px(300)}:h={height - px(64)}:color=0xE4E4E4@1.0:t=fill",
    ]
    # "Abas"/controles na barra de título.
    for index in range(3):
        parts.append(
            f"drawbox=x={px(40 + index * 90)}:y={px(22)}:w={px(60)}:h={px(20)}"
            ":color=0x8A8A8A@1.0:t=fill"
        )

    # Linhas de texto do corpo, reveladas ao longo do tempo.
    line_height = px(14)
    line_step = px(30)
    line_ys = list(range(px(100), height - px(40), line_step))
    # As revelações se espalham só pelos primeiros 90% da duração: assim a
    # última linha aparece com folga antes do fim, em vez de cair fora do
    # vídeo e nunca ser desenhada.
    reveal_span = spec.duration_s * 0.9
    for row, y in enumerate(line_ys):
        line_width = px(rnd.randint(180, 1180))
        indent = px(360 + (40 if rnd.random() < 0.25 else 0))
        appear_at = (row / max(1, len(line_ys) - 1)) * reveal_span
        parts.append(
            f"drawbox=x={indent}:y={y}:w={line_width}:h={line_height}"
            f":color=0x1E1E1E@1.0:t=fill:enable='gte(t,{appear_at:.3f})'"
        )

    # Itens da sidebar (estáticos).
    for index in range(14):
        item_y = px(110) + index * px(44)
        if item_y + px(12) >= height:
            break
        parts.append(
            f"drawbox=x={px(40)}:y={item_y}:w={px(rnd.randint(90, 220))}:h={px(12)}"
            ":color=0x666666@1.0:t=fill"
        )

    # Cursor piscando: garante que nenhum quadro seja bit-a-bit idêntico ao
    # anterior, evitando a fonte degenerada em que o x264 só emite skip frames.
    parts.append(
        f"drawbox=x={px(360)}:y={px(100)}:w={px(3)}:h={px(18)}"
        ":color=0x1E1E1E@1.0:t=fill:enable='lt(mod(t,1),0.5)'"
    )
    # Ruído leve de captura: sem ele o material é limpo demais para ser
    # representativo de uma gravação real.
    parts.append(f"noise=alls=2:allf=t+u:all_seed={spec.seed % 1000}")
    parts.append('format=yuv420p')
    return ','.join(parts)


def _motion_filter(spec: SourceSpec) -> str:
    """Alto movimento: padrão detalhado + rotação contínua + deslocamento.

    A rotação faz cada quadro divergir globalmente do anterior, que é o que
    torna a estimativa de movimento cara — o oposto da fonte de tela.
    """
    return (
        f"rotate=a=0.35*t:c=black:ow={spec.width}:oh={spec.height},"
        f"crop={spec.width}:{spec.height},"
        f"noise=alls=6:allf=t+u:all_seed={spec.seed % 1000},"
        "format=yuv420p"
    )


def _uhd_filter(spec: SourceSpec) -> str:
    """4K com detalhe fino e movimento moderado."""
    return (
        f"noise=alls=4:allf=t+u:all_seed={spec.seed % 1000},"
        "format=yuv420p"
    )


def _lavfi_video_input(spec: SourceSpec) -> str:
    """Fonte lavfi base de cada tipo de conteúdo."""
    if spec.kind == 'screen':
        return f"color=c=0xF2F2F2:s={spec.width}x{spec.height}:r={spec.fps}:d={spec.duration_s}"
    return (
        f"testsrc2=size={spec.width}x{spec.height}:rate={spec.fps}"
        f":duration={spec.duration_s}"
    )


def _video_filter(spec: SourceSpec) -> str:
    if spec.kind == 'screen':
        return _screen_filter(spec)
    if spec.kind == 'motion':
        return _motion_filter(spec)
    if spec.kind == 'uhd':
        return _uhd_filter(spec)
    # portrait: pixels em paisagem; a rotação entra como metadado no remux.
    return (
        f"noise=alls=3:allf=t+u:all_seed={spec.seed % 1000},"
        "format=yuv420p"
    )


def _audio_input(spec: SourceSpec) -> str:
    """Trilha de áudio real: o pipeline reencoda áudio em AAC 128k e isso
    entra no tamanho de saída, então a fonte precisa ter som."""
    return f"sine=frequency=300:sample_rate=48000:duration={spec.duration_s}"


# --------------------------------------------------------------------------
# Geração
# --------------------------------------------------------------------------

def ensure_sources(
    ffmpeg_path: str,
    ffprobe_path: str,
    specs: list,
    media_dir: Path,
    force: bool = False,
    log=print,
) -> list:
    """Garante que cada spec tenha um arquivo real em disco e devolve os metadados.

    O nome do arquivo carrega o hash do spec, então mudar qualquer parâmetro
    da receita gera um arquivo novo em vez de reaproveitar em silêncio um
    vídeo antigo — reaproveitar invalidaria a comparação com o baseline.
    """
    media_dir.mkdir(parents=True, exist_ok=True)
    generated = []

    for spec in specs:
        path = media_dir / spec.filename()
        if force or not path.exists():
            log(f"  gerando {spec.name} ({spec.width}x{spec.height}@{spec.fps}, "
                f"{spec.duration_s:g}s)...")
            _generate_source(ffmpeg_path, spec, path)
        else:
            log(f"  reaproveitando {path.name}")

        media = probe_media(ffprobe_path, str(path))
        generated.append({
            'spec': asdict(spec),
            'fingerprint': spec.fingerprint(),
            'path': str(path),
            'media': media,
        })

    return generated


def _generate_source(ffmpeg_path: str, spec: SourceSpec, path: Path):
    """Codifica o vídeo de origem (e, se for o caso, anexa a rotação no container)."""
    # Vídeos com rotação são codificados em paisagem e depois remuxados com o
    # display matrix, do mesmo jeito que test_rotation_metadata.py faz: é a
    # forma de obter rotação GENUÍNA de container, e não pixels já girados.
    encode_target = path.with_name(path.stem + '_flat.mp4') if spec.rotate_metadata else path

    cmd = [
        ffmpeg_path, '-y', '-hide_banner', '-nostdin', '-loglevel', 'error',
        '-f', 'lavfi', '-i', _lavfi_video_input(spec),
        '-f', 'lavfi', '-i', _audio_input(spec),
        '-vf', _video_filter(spec),
        '-c:v', 'libx264',
        '-crf', str(spec.source_crf),
        '-preset', spec.source_preset,
        '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '192k',
        '-shortest',
        '-movflags', '+faststart',
        str(encode_target),
    ]
    result = run_command(cmd, timeout=7200)
    if result.returncode != 0 or not encode_target.exists():
        raise RuntimeError(
            f"falha ao gerar {spec.name}: {(result.stderr or '').strip()[-600:]}")

    if not spec.rotate_metadata:
        return

    remux = [
        ffmpeg_path, '-y', '-hide_banner', '-nostdin', '-loglevel', 'error',
        '-display_rotation', str(spec.rotate_metadata),
        '-i', str(encode_target),
        '-c', 'copy',
        '-movflags', '+faststart',
        str(path),
    ]
    result = run_command(remux, timeout=600)
    if result.returncode != 0 or not path.exists():
        raise RuntimeError(
            f"falha ao remuxar rotação em {spec.name}: {(result.stderr or '').strip()[-600:]}")
    encode_target.unlink(missing_ok=True)
