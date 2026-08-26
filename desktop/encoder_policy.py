"""De (perfil + capabilities) para os parâmetros de encode do FFmpeg.

Este módulo é a **única** fonte dos argumentos de vídeo do pipeline. O
`compressor.py` não decide encoder: ele pergunta aqui e usa o que vier.

O ponto difícil: cada família de hardware tem seu próprio controle de qualidade,
e nenhum deles é CRF
---------------------------------------------------------------------------

| Família | Controle | Faixa | Sentido |
|---|---|---|---|
| libx264 | `-crf` | 0-51 | **menor = melhor** |
| VideoToolbox | `-q:v` | 0-100 | **maior = melhor** (invertido!) |
| NVENC | `-cq` (com `-rc vbr -b:v 0`) | 0-51 | menor = melhor |
| QSV | `-global_quality` | 1-51 | menor = melhor |
| AMF | `-qp_i`/`-qp_p` (com `-rc cqp`) | 0-51 | menor = melhor |

Traduzir CRF para cada um deles é aproximação, não conversão: os números não
significam a mesma coisa nem produzem o mesmo tamanho de arquivo. As tabelas
abaixo são **pontos de partida** para o benchmark medir, não verdades — o único
juiz é `desktop/tests/bench`.

Quando o hardware é recusado
----------------------------
Nem todo encoder de hardware oferece qualidade constante. Quando só há bitrate
alvo disponível (VideoToolbox em Mac Intel), o policy **não** usa hardware: o
benchmark mediu arquivos até 288% maiores e queda de 21,5 pontos de VMAF. O
número e o raciocínio estão em `ALLOW_BITRATE_HARDWARE`.

Por que "Alta Qualidade" nunca usa hardware
-------------------------------------------
Encoders de hardware são rápidos porque procuram menos: a mesma qualidade
percebida custa mais bits que no x264. Num app cujo propósito é **reduzir
tamanho**, trocar software por hardware no perfil de máxima fidelidade seria
piorar em silêncio exatamente aquilo que o usuário pediu ao escolher esse
perfil. Então `Alta Qualidade` é software, sempre. Ver `SOFTWARE_ONLY_PROFILES`.

Por que a saída continua H.264
------------------------------
HEVC comprime melhor, mas quebra compatibilidade em players e sites antigos, e
essa decisão é do produto, não desta camada. O suporte está implementado
(incluindo o `-tag:v hvc1`, sem o qual o arquivo não abre em device Apple) e
fica atrás de `prefer_hevc=True`, desligado por padrão.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Dict, Optional, Sequence, Tuple

from encoder_caps import VENDOR_OF, EncoderCapabilities

logger = logging.getLogger(__name__)

# Perfis que jamais aceitam encoder de hardware, por mais disponível que ele
# esteja. Ver a docstring do módulo.
SOFTWARE_ONLY_PROFILES: Tuple[str, ...] = ('Alta Qualidade',)

# Ordem de preferência de família por plataforma. A primeira que estiver
# *usável* (probe real aprovado, ver encoder_caps) ganha.
VENDOR_PREFERENCE: Dict[str, Tuple[str, ...]] = {
    'darwin': ('videotoolbox',),
    'win32': ('nvenc', 'qsv', 'amf'),
    'linux': ('nvenc', 'qsv'),
}

SOFTWARE_ENCODER = 'libx264'

# Aceitar encoder de hardware que só ofereça controle por BITRATE (sem
# qualidade constante). Desligado — e a razão está medida, não suposta.
#
# Benchmark de 2026-08-18 (Mac Intel, VideoToolbox em modo bitrate, quick,
# 4 fontes × 4 perfis, `desktop/tests/bench/results/`), hardware vs libx264:
#
#   tempo:   -45% a -70%   (2x a 3x mais rápido)
#   memória: -80% de pico de RSS
#   tamanho: +13% a +288%  <-- inaceitável
#   VMAF:    de +4,9 a -21,5 pontos
#
# O pior caso, `screen_1080p30 / Compressão Máxima`, saiu **288% maior**: o
# usuário pediu compressão máxima e recebeu um arquivo 3,9x maior que o do
# libx264. O segundo pior, `motion_1080p60 / Compressão Máxima`, perdeu **21,5
# pontos de VMAF** (83,3 -> 61,8), que é degradação visível.
#
# A causa é estrutural, não um ajuste ruim de parâmetro: bitrate alvo gasta os
# mesmos bits numa gravação de tela parada e numa cena de ação, enquanto o CRF
# gasta pouco na primeira e muito na segunda. Nenhuma tabela de bpp conserta
# isso — o número certo depende do conteúdo, que só o encoder vê.
#
# Num app cujo propósito é reduzir tamanho, trocar 2x de velocidade por 3,9x de
# tamanho é desfazer o produto. Então: hardware só com qualidade constante.
#
# ATENÇÃO: isto NÃO mede `-q:v` (Apple Silicon), `-cq` (NVENC) nem
# `-global_quality` (QSV), que se adaptam ao conteúdo e provavelmente se saem
# muito melhor. Esses continuam habilitados — e continuam **sem medição**, por
# falta de hardware para testá-los aqui. Rodar o bench numa dessas máquinas é
# pré-requisito para confiar neles.
ALLOW_BITRATE_HARDWARE = False

# Containers em que uma stream HEVC precisa da tag hvc1. Sem ela o arquivo é
# gravado como hev1 e o QuickTime/iOS/Safari se recusam a tocar.
_HVC1_CONTAINERS = ('.mp4', '.mov', '.m4v')


@dataclass(frozen=True)
class EncodePlan:
    """Os argumentos de vídeo escolhidos, e o porquê."""

    encoder: str
    vendor: str
    is_hardware: bool
    video_args: Tuple[str, ...]
    reason: str

    def describe(self) -> str:
        tipo = 'hardware' if self.is_hardware else 'software'
        return f"{self.encoder} ({tipo}, {self.vendor}): {self.reason}"


# --------------------------------------------------------- tradução de qualidade

# Bits por pixel por frame, por faixa de CRF. Usado só quando o encoder não
# oferece qualidade constante (VideoToolbox em Mac Intel — ver
# QUALITY_MODE_PROBES em encoder_caps).
#
# Bitrate é um substituto pior que CRF por natureza: gasta o mesmo em uma
# gravação de tela parada e numa cena de ação, quando o CRF gastaria pouco na
# primeira. É o que existe nessas máquinas.
_BPP_POR_CRF = ((20, 0.13), (25, 0.10), (30, 0.06), (99, 0.04))

# Resolução assumida quando o chamador não informa as dimensões. 1080p30 é o
# caso mais comum do app; sem isso o bitrate sairia arbitrário.
_DIMENSOES_PADRAO = (1920, 1080, 30.0)


def _bitrate_args(crf: int, width: int, height: int, fps: float) -> Tuple[str, ...]:
    """`-b:v`/`-maxrate`/`-bufsize` a partir de um alvo de bits por pixel."""
    if width <= 0 or height <= 0:
        width, height, fps = _DIMENSOES_PADRAO
    if fps <= 0:
        fps = _DIMENSOES_PADRAO[2]

    bpp = next(valor for limite, valor in _BPP_POR_CRF if crf <= limite)
    bitrate = int(width * height * fps * bpp)
    bitrate = max(300_000, min(bitrate, 60_000_000))

    return (
        '-b:v', f'{bitrate // 1000}k',
        '-maxrate', f'{int(bitrate * 1.5) // 1000}k',
        # bufsize = 2x o bitrate: janela de ~2 s, o suficiente para absorver
        # uma cena difícil sem deixar o pico estourar o alvo por muito tempo.
        '-bufsize', f'{int(bitrate * 2) // 1000}k',
    )


def _videotoolbox_quality(crf: int) -> int:
    """CRF (0-51, menor=melhor) -> `-q:v` do VideoToolbox (0-100, maior=melhor).

    Reta ancorada no intervalo que interessa: crf 23 -> 55 e crf 32 -> 35, os
    extremos do "sweet spot" praticado. Fora dele a reta é grampeada, porque
    extrapolar linearmente uma escala que nem é linear não ajudaria ninguém.
    """
    quality = round(55 - (crf - 23) * (20 / 9))
    return max(20, min(80, quality))


def _nvenc_preset(preset: str) -> str:
    """Preset do x264 -> preset p1..p7 do NVENC (p7 = mais lento/melhor)."""
    return {
        'ultrafast': 'p1', 'superfast': 'p1', 'veryfast': 'p2', 'faster': 'p3',
        'fast': 'p4', 'medium': 'p5', 'slow': 'p6', 'slower': 'p7', 'veryslow': 'p7',
    }.get(preset, 'p5')


def _qsv_preset(preset: str) -> str:
    return {
        'ultrafast': 'veryfast', 'superfast': 'veryfast', 'veryfast': 'veryfast',
        'faster': 'faster', 'fast': 'fast', 'medium': 'medium',
        'slow': 'slow', 'slower': 'slower', 'veryslow': 'veryslow',
    }.get(preset, 'medium')


def _amf_quality(preset: str) -> str:
    return {
        'ultrafast': 'speed', 'superfast': 'speed', 'veryfast': 'speed',
        'faster': 'speed', 'fast': 'balanced', 'medium': 'balanced',
        'slow': 'quality', 'slower': 'quality', 'veryslow': 'quality',
    }.get(preset, 'balanced')


def _args_for(encoder: str, crf: int, preset: str, quality_mode: str = 'quality',
              dimensions: Tuple[int, int, float] = _DIMENSOES_PADRAO) -> Tuple[str, ...]:
    """Argumentos de encode de um encoder concreto.

    ``quality_mode`` vem do probe (``EncoderCapabilities.quality_mode_of``) e diz
    se esta máquina aceita qualidade constante para este encoder.
    """
    vendor = VENDOR_OF.get(encoder, 'software')

    if vendor == 'videotoolbox':
        # Não existe CRF aqui. -q:v é qualidade constante, mas só funciona em
        # Apple Silicon: em Mac Intel o ffmpeg responde "-q:v qscale not
        # available for encoder. Use -b:v bitrate instead". O probe já
        # descobriu qual dos dois vale nesta máquina.
        if quality_mode == 'bitrate':
            return ('-c:v', encoder) + _bitrate_args(crf, *dimensions)
        return ('-c:v', encoder, '-q:v', str(_videotoolbox_quality(crf)))

    if vendor == 'nvenc':
        # -b:v 0 é obrigatório: sem ele o -cq vira apenas um teto dentro de um
        # VBR com bitrate alvo, e a qualidade deixa de ser constante.
        return (
            '-c:v', encoder,
            '-preset', _nvenc_preset(preset),
            '-tune', 'hq',
            '-rc', 'vbr',
            '-cq', str(crf),
            '-b:v', '0',
        )

    if vendor == 'qsv':
        # -global_quality sem bitrate alvo ativa o modo ICQ (qualidade constante).
        return (
            '-c:v', encoder,
            '-preset', _qsv_preset(preset),
            '-global_quality', str(crf),
        )

    if vendor == 'amf':
        return (
            '-c:v', encoder,
            '-rc', 'cqp',
            '-qp_i', str(crf), '-qp_p', str(crf),
            '-quality', _amf_quality(preset),
        )

    return ('-c:v', encoder, '-crf', str(crf), '-preset', preset)


def _container_args(encoder: str, output_file: str) -> Tuple[str, ...]:
    """Ajustes que dependem do container de saída."""
    if not encoder.startswith('hevc_'):
        return ()
    extension = os.path.splitext(output_file or '')[1].lower()
    if extension in _HVC1_CONTAINERS:
        return ('-tag:v', 'hvc1')
    return ()


# ------------------------------------------------------------------- política

def software_plan(config: Dict, reason: str = 'fallback de software') -> EncodePlan:
    """O plano de sempre: libx264. É para cá que tudo cai quando algo dá errado."""
    crf = int(config['crf'])
    preset = str(config['preset'])
    return EncodePlan(
        encoder=SOFTWARE_ENCODER,
        vendor='software',
        is_hardware=False,
        video_args=_args_for(SOFTWARE_ENCODER, crf, preset),
        reason=reason,
    )


def _hardware_candidate(caps: EncoderCapabilities, prefer_hevc: bool,
                        allow_bitrate_mode: bool = ALLOW_BITRATE_HARDWARE) -> Optional[str]:
    """Melhor encoder de hardware usável, na ordem de preferência da plataforma.

    Encoders que só oferecem bitrate são descartados por padrão — ver
    `ALLOW_BITRATE_HARDWARE`.
    """
    for vendor in VENDOR_PREFERENCE.get(caps.platform_key, ()):
        for codec in (('hevc', 'h264') if prefer_hevc else ('h264',)):
            encoder = f'{codec}_{vendor}'
            if not caps.can_use(encoder):
                continue
            if not allow_bitrate_mode and caps.quality_mode_of(encoder) == 'bitrate':
                continue
            return encoder
    return None


def _dimensions_from(video_info: Optional[Dict]) -> Tuple[int, int, float]:
    """(largura, altura, fps) a partir do dict de `get_video_info`."""
    if not video_info:
        return _DIMENSOES_PADRAO
    try:
        width = int(video_info.get('width') or 0)
        height = int(video_info.get('height') or 0)
        fps = float(video_info.get('fps') or 0)
    except (TypeError, ValueError):
        return _DIMENSOES_PADRAO
    if width <= 0 or height <= 0:
        return _DIMENSOES_PADRAO
    return width, height, fps or _DIMENSOES_PADRAO[2]


def plan_encode(profile: str,
                config: Dict,
                caps: Optional[EncoderCapabilities],
                output_file: str = '',
                video_info: Optional[Dict] = None,
                prefer_hevc: bool = False,
                allow_hardware: bool = True,
                allow_bitrate_hardware: bool = ALLOW_BITRATE_HARDWARE) -> EncodePlan:
    """Escolhe o encoder e monta os argumentos de vídeo.

    Args:
        profile: nome do perfil (`COMPRESSION_PROFILES`).
        config: o dict do perfil, com `crf` e `preset`.
        caps: capabilities detectadas, ou `None` se o probe ainda não terminou.
        output_file: caminho de saída — só para decidir a tag do container.
        video_info: dict de `get_video_info`. Só é consultado no modo bitrate,
            onde a resolução e o fps definem o alvo; ignorá-lo daria bitrate
            de 1080p a um vídeo 4K.
        prefer_hevc: tenta HEVC antes de H.264. Desligado por padrão.
        allow_hardware: `False` força software (usado no retry pós-falha).

    Nunca levanta exceção e nunca devolve `None`: no pior caso, libx264.
    """
    crf = int(config['crf'])
    preset = str(config['preset'])

    if not allow_hardware:
        return software_plan(config, 'hardware desabilitado para esta execução')

    if profile in SOFTWARE_ONLY_PROFILES:
        return software_plan(config, f"perfil '{profile}' é software por política")

    if caps is None:
        # Probe de background ainda rodando. Não esperar é proposital: melhor
        # exportar já em software do que segurar a UI por causa de otimização.
        return software_plan(config, 'capabilities ainda não detectadas')

    encoder = _hardware_candidate(caps, prefer_hevc, allow_bitrate_hardware)
    if encoder is None:
        # Distingue "não tem hardware" de "tem, mas só em modo bitrate" — são
        # diagnósticos diferentes e o segundo é uma decisão nossa, medida.
        if _hardware_candidate(caps, prefer_hevc, allow_bitrate_mode=True):
            return software_plan(
                config,
                'hardware só oferece controle por bitrate, que aumenta muito o '
                'arquivo (ver ALLOW_BITRATE_HARDWARE)'
            )
        return software_plan(config, 'nenhum encoder de hardware usável nesta máquina')

    quality_mode = caps.quality_mode_of(encoder)
    args = _args_for(
        encoder, crf, preset,
        quality_mode=quality_mode,
        dimensions=_dimensions_from(video_info),
    ) + _container_args(encoder, output_file)

    return EncodePlan(
        encoder=encoder,
        vendor=VENDOR_OF.get(encoder, 'desconhecido'),
        is_hardware=True,
        video_args=args,
        reason=f"aceleração {caps.tier} aprovada no probe, controle por {quality_mode}",
    )
