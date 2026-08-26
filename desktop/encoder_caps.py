"""Detecção, em runtime, de quais encoders esta máquina realmente consegue usar.

Por que isto existe
-------------------
O binário embutido do FFmpeg é o mesmo para todos os usuários de uma plataforma,
mas o *hardware* não é. Um build de Windows traz nvenc, amf e qsv compilados
juntos; ele lista os três em ``ffmpeg -encoders`` **independentemente** de a
máquina ter GPU NVIDIA, AMD ou Intel. Listagem não é disponibilidade.

Daí a distinção que este módulo mantém:

``listed``
    O encoder existe no build. Barato de descobrir (uma chamada), mas mente.

``usable``
    O encoder **codificou 10 frames de verdade e saiu com código 0**. Caro
    (um processo por encoder), mas é a única resposta confiável.

Casos reais que só o teste real pega: ``h264_nvenc`` listado num PC sem GPU
NVIDIA ou com driver velho; ``hevc_videotoolbox`` que existe em Macs Intel
antigos mas falha ao inicializar porque a GPU não tem o bloco de encode HEVC.
Se confiássemos na listagem, o usuário só descobriria o problema quando a
exportação dele falhasse.

Custo e cache
-------------
Testar N encoders custa N processos de ffmpeg (~0,2-2 s cada). Isso roda **uma
vez** e vai para disco, com chave derivada da versão do ffmpeg + plataforma +
arquitetura. Trocar o binário (ou levar o perfil para outra máquina) invalida o
cache sozinho.

Mesmo assim a detecção **nunca** roda na thread da UI: use
``start_background_detection()`` no startup e ``get_capabilities()`` onde o
resultado for necessário. Enquanto o probe não terminou, ``get_capabilities()``
devolve ``None`` e quem chama deve seguir com software — nunca esperar.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Sequence, Tuple

from utils import subprocess_no_window_kwargs

logger = logging.getLogger(__name__)

# Sobe quando o formato do cache ou o conjunto de candidatos muda, para que
# caches gravados por uma versão antiga do app sejam descartados.
SCHEMA_VERSION = 2

# Encoders que vale a pena testar, por plataforma. libx264 entra em todas
# porque é o fallback: se ele falhar, o problema é grande e é melhor saber.
#
# vaapi (Linux) está deliberadamente fora: exige ``-vaapi_device`` e um grafo de
# filtros próprio (hwupload), então um probe genérico daria falso negativo. Só
# faz sentido adicionar junto com o suporte real no encoder_policy.
_CANDIDATES: Dict[str, Tuple[str, ...]] = {
    'darwin': ('libx264', 'h264_videotoolbox', 'hevc_videotoolbox'),
    'win32': (
        'libx264',
        'h264_nvenc', 'hevc_nvenc',
        'h264_qsv', 'hevc_qsv',
        'h264_amf', 'hevc_amf',
    ),
    'linux': ('libx264', 'h264_nvenc', 'hevc_nvenc', 'h264_qsv', 'hevc_qsv'),
}

# Família de hardware de cada encoder. Usado para o "tier" e pelo policy.
VENDOR_OF: Dict[str, str] = {
    'h264_videotoolbox': 'videotoolbox', 'hevc_videotoolbox': 'videotoolbox',
    'h264_nvenc': 'nvenc', 'hevc_nvenc': 'nvenc',
    'h264_qsv': 'qsv', 'hevc_qsv': 'qsv',
    'h264_amf': 'amf', 'hevc_amf': 'amf',
    'libx264': 'software', 'libx265': 'software',
}

PROBE_TIMEOUT_S = 30

# Modos de controle de qualidade a testar, por família, em ordem de preferência.
#
# Probar `-c:v h264_videotoolbox` sozinho NÃO prova que
# `-c:v h264_videotoolbox -q:v 55` funciona — e essa diferença não é teórica:
# em Mac Intel o ffmpeg recusa o segundo com "-q:v qscale not available for
# encoder. Use -b:v bitrate instead", porque qualidade constante no VideoToolbox
# exige Apple Silicon. Um probe sem os parâmetros reais aprova um encoder que a
# exportação não consegue usar, e o usuário paga uma tentativa perdida em toda
# exportação.
#
# Então o probe roda com os mesmos argumentos que o encoder_policy emite, e o
# que fica registrado é qual modo passou. 'quality' = qualidade constante;
# 'bitrate' = bitrate alvo (adapta-se pior ao conteúdo, mas é o que resta).
QUALITY_MODE_PROBES: Dict[str, Tuple[Tuple[str, Tuple[str, ...]], ...]] = {
    'videotoolbox': (
        ('quality', ('-q:v', '55')),
        ('bitrate', ('-b:v', '2M', '-maxrate', '3M', '-bufsize', '4M')),
    ),
    'nvenc': (('quality', ('-rc', 'vbr', '-cq', '23', '-b:v', '0')),),
    'qsv': (('quality', ('-global_quality', '23')),),
    'amf': (('quality', ('-rc', 'cqp', '-qp_i', '23', '-qp_p', '23')),),
    'software': (('quality', ('-crf', '23')),),
}

# Resolução do vídeo de teste. NÃO diminua sem medir.
#
# Encoders de hardware têm resolução mínima, e ela varia por codec e por GPU:
# neste projeto, um Mac Intel reprovou `h264_videotoolbox` a 320x240 com
# "Cannot create compression session: -12903" e passou a 640x480 e 720p — com
# `hevc_videotoolbox` passando nos três. Probar pequeno demais inventa encoders
# quebrados que funcionam perfeitamente no vídeo real do usuário, que é o
# oposto do trabalho deste módulo.
#
# 720p custa ~0,05 s a mais por encoder que 480p (medido), e o probe inteiro
# roda uma vez e vai para o cache. Não vale economizar aqui.
PROBE_SIZE = '1280x720'
PROBE_FRAMES = 10


@dataclass(frozen=True)
class EncoderCapabilities:
    """O que esta máquina consegue fazer. Imutável: é um retrato de um momento."""

    ffmpeg_path: str = ''
    ffmpeg_version: str = ''
    platform_key: str = ''
    machine: str = ''
    listed_encoders: Tuple[str, ...] = ()
    usable_encoders: Tuple[str, ...] = ()
    hw_decoders: Tuple[str, ...] = ()
    tier: str = 'software'
    # encoder -> modo de controle de qualidade que passou no probe
    # ('quality' ou 'bitrate'). Ver QUALITY_MODE_PROBES.
    quality_modes: Dict[str, str] = field(default_factory=dict)
    probe_failures: Dict[str, str] = field(default_factory=dict)
    probed_at: float = 0.0
    from_cache: bool = False

    def can_use(self, encoder: str) -> bool:
        return encoder in self.usable_encoders

    def quality_mode_of(self, encoder: str) -> str:
        """Como pedir qualidade a este encoder nesta máquina. Default: 'quality'."""
        return self.quality_modes.get(encoder, 'quality')

    def usable_vendors(self) -> Tuple[str, ...]:
        seen = []
        for enc in self.usable_encoders:
            vendor = VENDOR_OF.get(enc, 'software')
            if vendor != 'software' and vendor not in seen:
                seen.append(vendor)
        return tuple(seen)

    def summary(self) -> str:
        hw = [
            f"{e}[{self.quality_mode_of(e)}]"
            for e in self.usable_encoders
            if VENDOR_OF.get(e, 'software') != 'software'
        ]
        return (
            f"tier={self.tier} "
            f"hw={'+'.join(hw) if hw else 'nenhum'} "
            f"reprovados={len(self.probe_failures)}"
        )


def list_encoders(ffmpeg_path: str) -> Dict[str, str]:
    """Nome -> descrição de tudo que ``ffmpeg -encoders`` reporta.

    Só diz o que foi **compilado** no binário. Ver a docstring do módulo para o
    porquê de isso não bastar.
    """
    try:
        result = subprocess.run(
            [ffmpeg_path, '-hide_banner', '-encoders'],
            capture_output=True, text=True, timeout=PROBE_TIMEOUT_S,
            **subprocess_no_window_kwargs()
        )
    except Exception:
        logger.exception("Não foi possível listar encoders de %s", ffmpeg_path)
        return {}
    if result.returncode != 0:
        logger.warning("ffmpeg -encoders saiu com %s", result.returncode)
        return {}

    encoders: Dict[str, str] = {}
    # Formato: " V....D name   descrição". A tabela começa depois de "------".
    for line in (result.stdout or '').splitlines():
        match = re.match(r'^\s*([VAS][\w.]{5})\s+(\S+)\s*(.*)$', line)
        if match:
            encoders[match.group(2)] = match.group(3).strip()
    return encoders


def list_hw_decoders(ffmpeg_path: str) -> Tuple[str, ...]:
    """Métodos de aceleração de *decode* (``ffmpeg -hwaccels``)."""
    try:
        result = subprocess.run(
            [ffmpeg_path, '-hide_banner', '-hwaccels'],
            capture_output=True, text=True, timeout=PROBE_TIMEOUT_S,
            **subprocess_no_window_kwargs()
        )
    except Exception:
        return ()
    if result.returncode != 0:
        return ()

    names = []
    for line in (result.stdout or '').splitlines():
        line = line.strip()
        # A primeira linha é o cabeçalho "Hardware acceleration methods:".
        if not line or line.endswith(':'):
            continue
        names.append(line)
    return tuple(names)


def probe_encoder(ffmpeg_path: str, encoder: str,
                  extra_args: Sequence[str] = (),
                  timeout: int = PROBE_TIMEOUT_S) -> Tuple[bool, str]:
    """Testa o encoder **de verdade**: encoda frames de testsrc2 e exige exit 0.

    Retorna ``(ok, motivo_da_falha)``. A saída vai para o muxer ``null``, então
    nada toca o disco — o que se mede é a inicialização do encoder, que é
    exatamente onde um encoder "presente mas inutilizável" quebra.

    ``extra_args`` são os argumentos de controle de qualidade — passe os mesmos
    que o encoder_policy vai emitir, senão o probe aprova uma configuração
    diferente da que será usada (ver ``QUALITY_MODE_PROBES``).

    Ver ``PROBE_SIZE`` para por que a resolução do teste não é arbitrária.
    """
    cmd = [
        ffmpeg_path, '-hide_banner', '-nostdin', '-loglevel', 'error',
        '-f', 'lavfi', '-i', f'testsrc2=size={PROBE_SIZE}:rate=30',
        '-frames:v', str(PROBE_FRAMES),
        '-pix_fmt', 'yuv420p',
        '-c:v', encoder, *extra_args,
        '-f', 'null', '-',
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            **subprocess_no_window_kwargs()
        )
    except subprocess.TimeoutExpired:
        return False, f"timeout de {timeout}s"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"

    if result.returncode == 0:
        return True, ''

    # A última linha de erro do ffmpeg é a informativa ("Cannot load
    # nvcuda.dll", "Error while opening encoder", ...).
    stderr = (result.stderr or '').strip()
    reason = stderr.splitlines()[-1].strip() if stderr else f"exit {result.returncode}"
    return False, reason[:200]


def _ffmpeg_version(ffmpeg_path: str) -> str:
    try:
        result = subprocess.run(
            [ffmpeg_path, '-hide_banner', '-version'],
            capture_output=True, text=True, timeout=PROBE_TIMEOUT_S,
            **subprocess_no_window_kwargs()
        )
    except Exception:
        return ''
    if result.returncode != 0:
        return ''
    first = (result.stdout or '').splitlines()
    return first[0].strip() if first else ''


def _candidates_for(platform_key: str) -> Tuple[str, ...]:
    return _CANDIDATES.get(platform_key, ('libx264',))


def _tier_for(usable: Sequence[str]) -> str:
    """Nome curto da melhor aceleração disponível. Só rótulo, não é política."""
    for vendor in ('videotoolbox', 'nvenc', 'qsv', 'amf'):
        if any(VENDOR_OF.get(enc) == vendor for enc in usable):
            return vendor
    return 'software'


# ---------------------------------------------------------------- cache em disco

def _cache_dir() -> str:
    if sys.platform == 'win32':
        base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
    elif sys.platform == 'darwin':
        base = os.path.join(os.path.expanduser('~'), 'Library', 'Caches')
    else:
        base = os.environ.get('XDG_CACHE_HOME') or os.path.join(os.path.expanduser('~'), '.cache')
    return os.path.join(base, 'comprimir-videos')


def _cache_key(ffmpeg_version: str, platform_key: str, machine: str,
               candidates: Sequence[str]) -> str:
    """Identidade do ambiente testado.

    Inclui a versão do ffmpeg porque trocar o binário pode acrescentar ou tirar
    encoders, e a arquitetura porque o mesmo Mac roda x86_64 sob Rosetta e
    arm64 nativo com resultados diferentes.
    """
    raw = '\x00'.join([
        str(SCHEMA_VERSION), ffmpeg_version, platform_key, machine,
        # A resolução do probe entra na chave porque mudá-la muda o veredito
        # (ver PROBE_SIZE): um cache gravado com 320x240 reprovaria encoders
        # que 720p aprova.
        PROBE_SIZE, str(PROBE_FRAMES),
        *candidates,
    ])
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:32]


def _cache_path() -> str:
    return os.path.join(_cache_dir(), 'encoder_caps.json')


def _load_cache(key: str) -> Optional[EncoderCapabilities]:
    try:
        with open(_cache_path(), 'r', encoding='utf-8') as handle:
            payload = json.load(handle)
    except (OSError, ValueError):
        return None

    if payload.get('key') != key:
        return None
    data = payload.get('caps')
    if not isinstance(data, dict):
        return None

    try:
        return EncoderCapabilities(
            **{
                **data,
                'listed_encoders': tuple(data.get('listed_encoders', ())),
                'usable_encoders': tuple(data.get('usable_encoders', ())),
                'hw_decoders': tuple(data.get('hw_decoders', ())),
                'from_cache': True,
            }
        )
    except TypeError:
        # Cache gravado por uma versão com outro conjunto de campos.
        return None


def _save_cache(key: str, caps: EncoderCapabilities) -> None:
    data = asdict(caps)
    data['from_cache'] = False
    for name in ('listed_encoders', 'usable_encoders', 'hw_decoders'):
        data[name] = list(data[name])
    try:
        os.makedirs(_cache_dir(), exist_ok=True)
        temp = _cache_path() + '.new'
        with open(temp, 'w', encoding='utf-8') as handle:
            json.dump({'key': key, 'caps': data}, handle, indent=2)
        os.replace(temp, _cache_path())
    except OSError:
        # Cache é otimização; não poder gravar não é motivo para falhar nada.
        logger.debug("Não foi possível gravar o cache de capabilities.", exc_info=True)


# ---------------------------------------------------------------- API principal

def detect_capabilities(ffmpeg_path: str, force: bool = False,
                        use_cache: bool = True) -> EncoderCapabilities:
    """Descobre o que a máquina suporta. Usa cache em disco quando possível.

    Nunca levanta exceção: no pior caso devolve capabilities só com software, e
    o policy cai em libx264.
    """
    platform_key = sys.platform
    machine = platform.machine()
    candidates = _candidates_for(platform_key)
    version = _ffmpeg_version(ffmpeg_path)
    key = _cache_key(version, platform_key, machine, candidates)

    if use_cache and not force:
        cached = _load_cache(key)
        if cached is not None:
            logger.info("Capabilities de encoder vindas do cache: %s", cached.summary())
            return cached

    listed = list_encoders(ffmpeg_path)
    usable: List[str] = []
    failures: Dict[str, str] = {}
    modes: Dict[str, str] = {}

    for encoder in candidates:
        if encoder not in listed:
            failures[encoder] = 'não existe neste build'
            continue

        vendor = VENDOR_OF.get(encoder, 'software')
        variants = QUALITY_MODE_PROBES.get(vendor, (('quality', ()),))
        started = time.monotonic()
        motivos = []

        for mode, extra_args in variants:
            ok, reason = probe_encoder(ffmpeg_path, encoder, extra_args)
            if ok:
                usable.append(encoder)
                modes[encoder] = mode
                logger.debug("probe %s [%s]: ok (%.2fs)", encoder, mode,
                             time.monotonic() - started)
                break
            motivos.append(f"{mode}: {reason}")
        else:
            failures[encoder] = ' | '.join(motivos)
            # Listado mas quebrado é o caso interessante: vale um INFO, porque
            # explica por que o usuário não está recebendo aceleração.
            logger.info("probe %s: REPROVADO (%.2fs) - %s", encoder,
                        time.monotonic() - started, failures[encoder])
            continue

        if modes[encoder] != variants[0][0]:
            # Passou, mas não no modo preferido. Vale registrar: é a diferença
            # entre qualidade constante e bitrate fixo.
            logger.info("probe %s: modo '%s' (o preferido '%s' não funciona aqui)",
                        encoder, modes[encoder], variants[0][0])

    caps = EncoderCapabilities(
        ffmpeg_path=ffmpeg_path,
        ffmpeg_version=version,
        platform_key=platform_key,
        machine=machine,
        listed_encoders=tuple(sorted(listed)),
        usable_encoders=tuple(usable),
        hw_decoders=list_hw_decoders(ffmpeg_path),
        tier=_tier_for(usable),
        quality_modes=modes,
        probe_failures=failures,
        probed_at=time.time(),
        from_cache=False,
    )

    if use_cache:
        _save_cache(key, caps)
    logger.info("Capabilities de encoder detectadas: %s", caps.summary())
    return caps


# ------------------------------------------------- detecção em background

_lock = threading.Lock()
_caps: Optional[EncoderCapabilities] = None
_thread: Optional[threading.Thread] = None


def start_background_detection(ffmpeg_path: str, force: bool = False) -> None:
    """Dispara a detecção numa thread daemon. Retorna na hora.

    Chamada no startup. A UI não espera: até o probe terminar,
    ``get_capabilities()`` devolve ``None`` e o pipeline usa software.
    """
    global _thread

    with _lock:
        if _thread is not None and _thread.is_alive():
            return

        def run() -> None:
            global _caps
            try:
                detected = detect_capabilities(ffmpeg_path, force=force)
            except Exception:
                logger.exception("Detecção de capabilities falhou; assumindo só software.")
                detected = EncoderCapabilities(
                    ffmpeg_path=ffmpeg_path, platform_key=sys.platform,
                    machine=platform.machine(), usable_encoders=('libx264',),
                )
            with _lock:
                _caps = detected

        _thread = threading.Thread(target=run, name='encoder-caps-probe', daemon=True)
        _thread.start()


def get_capabilities(timeout: float = 0.0) -> Optional[EncoderCapabilities]:
    """Capabilities já detectadas, ou ``None`` se ainda não terminou.

    ``timeout=0`` (padrão) **nunca** bloqueia — é o que a UI deve usar. Um
    timeout maior espera o probe de background; só use fora da thread da UI.
    """
    with _lock:
        if _caps is not None:
            return _caps
        thread = _thread

    if timeout > 0 and thread is not None:
        thread.join(timeout)

    with _lock:
        return _caps


def set_capabilities_for_test(caps: Optional[EncoderCapabilities]) -> None:
    """Injeta capabilities. Existe para os testes; não usar em produção."""
    global _caps, _thread
    with _lock:
        _caps = caps
        _thread = None
