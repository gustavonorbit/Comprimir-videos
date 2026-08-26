"""
Infraestrutura de medição do benchmark: captura de ambiente, sondagem de
mídia via ffprobe, amostragem de pico de RSS e cálculo de qualidade com
libvmaf.

Nada aqui é mock: todo número devolvido vem de um processo ffmpeg/ffprobe
real rodando sobre um arquivo real em disco.
"""

import ctypes
import json
import os
import platform
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from utils import subprocess_no_window_kwargs  # noqa: E402

try:
    import psutil  # type: ignore
    _PSUTIL = True
except ImportError:  # opcional; há fallback nativo em todo SO suportado
    psutil = None  # type: ignore
    _PSUTIL = False

# Amostragem de RSS: intervalo curto o suficiente para pegar o pico do x264
# (que aloca o grosso da memória logo no início, ao montar os buffers de
# lookahead) sem que o custo de amostrar polua o wall time medido.
RSS_SAMPLE_INTERVAL_S = 0.25


def run_command(cmd: list, timeout: Optional[float] = None) -> subprocess.CompletedProcess:
    """Executa um processo capturando saída, com os kwargs de janela do projeto."""
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        **subprocess_no_window_kwargs()
    )


# --------------------------------------------------------------------------
# Ambiente
# --------------------------------------------------------------------------

def _binary_version(binary_path: str) -> dict:
    """Extrai versão e linha de configuração do build de um binário ffmpeg/ffprobe."""
    try:
        result = run_command([binary_path, '-version'], timeout=15)
    except Exception as exc:  # binário ausente/corrompido
        return {'version': None, 'error': str(exc)}

    output = result.stdout or result.stderr or ""
    lines = output.splitlines()
    version = lines[0].strip() if lines else None

    configuration = ""
    for line in lines:
        if line.startswith('configuration:'):
            configuration = line[len('configuration:'):].strip()
            break

    return {
        'version_line': version,
        'version': _short_version(version),
        'configuration': configuration,
        'has_libvmaf': '--enable-libvmaf' in configuration,
        'has_libx264': '--enable-libx264' in configuration,
        'has_libfreetype': '--enable-libfreetype' in configuration,
    }


def _short_version(version_line: Optional[str]) -> Optional[str]:
    """'ffmpeg version 8.1 Copyright...' -> '8.1'."""
    if not version_line:
        return None
    match = re.match(r'\S+ version (\S+)', version_line)
    return match.group(1) if match else None


def _is_bundled(binary_path: str) -> bool:
    """True se o binário é o embutido em ``desktop/bin`` (e não o do sistema).

    Distinguir os dois é essencial para comparar dois JSONs: um baseline
    medido com o ffmpeg do Homebrew não é comparável com um medido com o
    binário que de fato vai junto no app.
    """
    bundled_dir = Path(__file__).resolve().parents[2] / 'bin'
    try:
        return Path(binary_path).resolve().parent == bundled_dir.resolve()
    except OSError:
        return False


def collect_environment(ffmpeg_path: str, ffprobe_path: str) -> dict:
    """Reúne tudo que faz um número de benchmark ser (ou não) comparável com outro."""
    return {
        'platform': {
            'system': platform.system(),
            'release': platform.release(),
            'version': platform.version(),
            'machine': platform.machine(),
            'processor': platform.processor(),
            'platform': platform.platform(),
            'python_version': platform.python_version(),
        },
        'cpu_logical_cores': os.cpu_count(),
        'ffmpeg': {
            'path': ffmpeg_path,
            'is_bundled': _is_bundled(ffmpeg_path),
            **_binary_version(ffmpeg_path),
        },
        'ffprobe': {
            'path': ffprobe_path,
            'is_bundled': _is_bundled(ffprobe_path),
            **_binary_version(ffprobe_path),
        },
    }


# --------------------------------------------------------------------------
# Sondagem de mídia
# --------------------------------------------------------------------------

def probe_media(ffprobe_path: str, file_path: str, count_frames: bool = False) -> dict:
    """Dimensões/fps/contagem de frames reais do arquivo, via ffprobe.

    A contagem de frames sai de ``nb_frames`` (metadado do container, leitura
    instantânea). ``count_frames=True`` força ``-count_frames``, que decodifica
    o arquivo inteiro e dá a contagem exata — vários minutos num 4K, então só
    vale a pena quando o container não traz ``nb_frames``. O fallback final é
    ``duração x fps``, e ``frames_source`` registra de onde o número veio.
    """
    entries = (
        'stream=width,height,r_frame_rate,avg_frame_rate,nb_frames,duration,pix_fmt:'
        'stream_side_data=rotation:stream_tags=rotate:'
        'format=duration,bit_rate'
    )
    if count_frames:
        entries = entries.replace('nb_frames', 'nb_frames,nb_read_frames')

    cmd = [ffprobe_path, '-v', 'error', '-select_streams', 'v:0']
    if count_frames:
        cmd.append('-count_frames')
    cmd += ['-show_entries', entries, '-of', 'json', file_path]

    result = run_command(cmd, timeout=3600)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe falhou em {file_path}: {result.stderr.strip()[-400:]}")

    data = json.loads(result.stdout)
    stream = (data.get('streams') or [{}])[0]
    fmt = data.get('format') or {}

    duration = _to_float(stream.get('duration')) or _to_float(fmt.get('duration')) or 0.0
    size_bytes = os.path.getsize(file_path)
    fps = _parse_rate(stream.get('r_frame_rate'))

    frames = _to_float(stream.get('nb_read_frames'))
    frames_source = 'count_frames'
    if not frames:
        frames = _to_float(stream.get('nb_frames'))
        frames_source = 'container'
    if not frames:
        frames = round(duration * fps) if (duration and fps) else 0
        frames_source = 'estimated'

    # Dimensões de exibição vs. armazenadas: num vídeo de celular com rotação
    # 90 no display matrix, o stream guarda 1920x1080 mas tudo (prévia, filtros,
    # export, VMAF) opera em 1080x1920. Registrar as duas evita ler o JSON e
    # concluir que o pipeline "girou" um vídeo que já nasceu girado.
    stored_width = int(stream.get('width') or 0)
    stored_height = int(stream.get('height') or 0)
    rotation = _display_rotation(stream)
    if rotation in (90, 270):
        display_width, display_height = stored_height, stored_width
    else:
        display_width, display_height = stored_width, stored_height

    return {
        'width': display_width,
        'height': display_height,
        'stored_width': stored_width,
        'stored_height': stored_height,
        'display_rotation': rotation,
        'pix_fmt': stream.get('pix_fmt'),
        'fps': fps,
        'avg_fps': _parse_rate(stream.get('avg_frame_rate')),
        'frames': int(frames or 0),
        'frames_source': frames_source,
        'duration_s': round(duration, 3),
        'size_bytes': size_bytes,
        'bitrate_kbps': round(size_bytes * 8 / duration / 1000, 1) if duration > 0 else None,
    }


def _display_rotation(stream: dict) -> int:
    """Rotação de exibição (0/90/180/270) a partir do display matrix ou da tag.

    Mesma normalização de ``VideoCompressor._display_rotation``: o ffmpeg pode
    reportar o ângulo como negativo (ex: -90).
    """
    raw = None
    for side_data in stream.get('side_data_list') or []:
        if 'rotation' in side_data:
            raw = side_data.get('rotation')
            break
    if raw is None:
        raw = (stream.get('tags') or {}).get('rotate')
    if raw is None:
        return 0
    try:
        return int(round(float(raw))) % 360
    except (TypeError, ValueError):
        return 0


def _to_float(value) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_rate(rate: Optional[str]) -> Optional[float]:
    """'30000/1001' -> 29.97."""
    if not rate or '/' not in rate:
        return _to_float(rate)
    num, den = rate.split('/', 1)
    num_f, den_f = _to_float(num), _to_float(den)
    if not num_f or not den_f:
        return None
    return round(num_f / den_f, 3)


# --------------------------------------------------------------------------
# Pico de RSS
# --------------------------------------------------------------------------

class PeakRssSampler:
    """Mede o pico de memória residente do processo ffmpeg disparado pelo pipeline.

    O ``compress_video`` cria o subprocesso internamente e o guarda em
    ``compressor.process``; como esta harness não pode alterar o compressor,
    a medição é feita de fora: uma thread espera o pid aparecer e passa a
    amostrar o processo até ele morrer.

    No Windows o número é EXATO — ``PeakWorkingSetSize`` é contabilizado pelo
    próprio kernel. Em macOS/Linux é o máximo das amostras, então um pico mais
    curto que ``RSS_SAMPLE_INTERVAL_S`` pode passar despercebido; por isso o
    JSON registra ``method`` e ``samples`` junto do valor.
    """

    def __init__(self, pid_getter, interval_s: float = RSS_SAMPLE_INTERVAL_S):
        self._pid_getter = pid_getter
        self._interval = interval_s
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.peak_bytes = 0
        self.samples = 0
        self.method = 'psutil' if _PSUTIL else ('windows_api' if os.name == 'nt' else 'ps')

    def __enter__(self):
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc_info):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        return False

    def _loop(self):
        pid = None
        # Espera o pipeline disparar o ffmpeg (o pid só existe depois do Popen).
        while pid is None and not self._stop.is_set():
            pid = self._pid_getter()
            if pid is None:
                time.sleep(0.02)
        if pid is None:
            return

        if os.name == 'nt' and not _PSUTIL:
            self._sample_windows(pid)
            return

        while not self._stop.is_set():
            rss = _read_rss_bytes(pid)
            if rss is None:  # processo terminou
                break
            self.samples += 1
            self.peak_bytes = max(self.peak_bytes, rss)
            self._stop.wait(self._interval)

    def _sample_windows(self, pid: int):
        """Mantém um handle aberto para ler o pico contabilizado pelo kernel.

        O handle segura o objeto-processo vivo depois do exit, então a última
        leitura devolve o pico real de toda a execução, não uma amostra.
        """
        handle = _win_open_process(pid)
        if handle is None:
            return
        try:
            while not self._stop.is_set():
                peak = _win_peak_working_set(handle)
                if peak is None:
                    break
                self.samples += 1
                self.peak_bytes = max(self.peak_bytes, peak)
                if not _win_process_alive(handle):
                    break
                self._stop.wait(self._interval)
            final = _win_peak_working_set(handle)
            if final:
                self.peak_bytes = max(self.peak_bytes, final)
        finally:
            _win_close_handle(handle)

    def result(self) -> dict:
        return {
            'peak_rss_bytes': self.peak_bytes or None,
            'peak_rss_mb': round(self.peak_bytes / (1024 * 1024), 2) if self.peak_bytes else None,
            'method': self.method,
            'samples': self.samples,
            'sample_interval_s': self._interval,
        }


def _read_rss_bytes(pid: int) -> Optional[int]:
    """RSS atual do pid em bytes, ou None se o processo não existe mais."""
    if _PSUTIL:
        try:
            return psutil.Process(pid).memory_info().rss
        except Exception:
            return None

    if os.name == 'nt':
        handle = _win_open_process(pid)
        if handle is None:
            return None
        try:
            return _win_peak_working_set(handle)
        finally:
            _win_close_handle(handle)

    try:
        result = run_command(['ps', '-o', 'rss=', '-p', str(pid)], timeout=5)
    except Exception:
        return None
    value = (result.stdout or '').strip()
    if not value:
        return None
    try:
        return int(value.split()[0]) * 1024  # ps reporta em KB
    except (ValueError, IndexError):
        return None


class _ProcessMemoryCounters(ctypes.Structure):
    _fields_ = [
        ('cb', ctypes.c_ulong),
        ('PageFaultCount', ctypes.c_ulong),
        ('PeakWorkingSetSize', ctypes.c_size_t),
        ('WorkingSetSize', ctypes.c_size_t),
        ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
        ('QuotaPagedPoolUsage', ctypes.c_size_t),
        ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
        ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
        ('PagefileUsage', ctypes.c_size_t),
        ('PeakPagefileUsage', ctypes.c_size_t),
    ]


def _win_kernel32():
    """kernel32 com as assinaturas declaradas.

    Declarar ``restype``/``argtypes`` não é cosmético aqui: sem isso o ctypes
    assume que ``OpenProcess`` devolve um ``int`` de 32 bits e trunca o HANDLE
    de 64 bits do Windows x64 — o handle truncado às vezes ainda funciona, o
    que renderia uma medição de memória que falha de forma intermitente.
    """
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel32.CloseHandle.restype = ctypes.c_int
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.K32GetProcessMemoryInfo.restype = ctypes.c_int
    kernel32.K32GetProcessMemoryInfo.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(_ProcessMemoryCounters), ctypes.c_ulong]
    kernel32.GetExitCodeProcess.restype = ctypes.c_int
    kernel32.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    return kernel32


def _win_open_process(pid: int):
    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_VM_READ = 0x0010
    handle = _win_kernel32().OpenProcess(
        PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, 0, pid)
    return handle or None


def _win_close_handle(handle):
    _win_kernel32().CloseHandle(handle)


def _win_peak_working_set(handle) -> Optional[int]:
    counters = _ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(_ProcessMemoryCounters)
    ok = _win_kernel32().K32GetProcessMemoryInfo(
        handle, ctypes.byref(counters), counters.cb)
    return int(counters.PeakWorkingSetSize) if ok else None


def _win_process_alive(handle) -> bool:
    STILL_ACTIVE = 259
    code = ctypes.c_ulong()
    if not _win_kernel32().GetExitCodeProcess(handle, ctypes.byref(code)):
        return False
    return code.value == STILL_ACTIVE


# --------------------------------------------------------------------------
# Qualidade (libvmaf)
# --------------------------------------------------------------------------

def measure_vmaf(
    ffmpeg_path: str,
    reference: str,
    distorted: str,
    log_path: str,
    n_threads: Optional[int] = None,
    n_subsample: int = 1,
    timeout: Optional[float] = None,
) -> dict:
    """Compara ``distorted`` com ``reference`` usando libvmaf, com PSNR junto.

    O ``setpts=PTS-STARTPTS`` nos dois lados alinha o início dos streams: sem
    isso, um offset de timestamp faria o framesync parear frames trocados e
    derrubar o VMAF por um motivo que não é perda de qualidade.

    Vídeos com rotação de metadados funcionam sem tratamento especial: o
    ffmpeg auto-rotaciona referência e distorcido na decodificação, então os
    dois chegam ao libvmaf já na orientação de exibição (verificado com o
    perfil ``portrait_rotado``).
    """
    threads = n_threads or os.cpu_count() or 4
    log_path_escaped = _escape_filter_path(log_path)

    libvmaf_args = (
        f"libvmaf=log_path={log_path_escaped}:log_fmt=json"
        f":feature='name=psnr':n_threads={threads}:n_subsample={n_subsample}"
    )
    filtergraph = (
        "[0:v]setpts=PTS-STARTPTS[dist];"
        "[1:v]setpts=PTS-STARTPTS[ref];"
        f"[dist][ref]{libvmaf_args}"
    )

    cmd = [
        ffmpeg_path, '-y', '-hide_banner', '-nostdin',
        '-i', distorted,
        '-i', reference,
        '-lavfi', filtergraph,
        '-f', 'null', '-',
    ]

    started = time.perf_counter()
    result = run_command(cmd, timeout=timeout)
    elapsed = time.perf_counter() - started

    if result.returncode != 0 or not os.path.exists(log_path):
        return {
            'ok': False,
            'error': (result.stderr or '').strip()[-400:],
            'elapsed_s': round(elapsed, 3),
        }

    with open(log_path, 'r', encoding='utf-8') as handle:
        data = json.load(handle)

    scores = [
        frame['metrics']['vmaf']
        for frame in data.get('frames', [])
        if 'vmaf' in frame.get('metrics', {})
    ]
    pooled = data.get('pooled_metrics', {})

    return {
        'ok': True,
        'mean': _round(pooled.get('vmaf', {}).get('mean')),
        'min': _round(pooled.get('vmaf', {}).get('min')),
        'max': _round(pooled.get('vmaf', {}).get('max')),
        'harmonic_mean': _round(pooled.get('vmaf', {}).get('harmonic_mean')),
        'low_1pct': _round(low_percentile_mean(scores, 0.01)),
        'psnr_y_mean': _round(pooled.get('psnr_y', {}).get('mean')),
        'psnr_cb_mean': _round(pooled.get('psnr_cb', {}).get('mean')),
        'psnr_cr_mean': _round(pooled.get('psnr_cr', {}).get('mean')),
        'frames_scored': len(scores),
        'n_subsample': n_subsample,
        'model': 'vmaf_v0.6.1',
        'elapsed_s': round(elapsed, 3),
    }


def low_percentile_mean(scores: list, fraction: float = 0.01) -> Optional[float]:
    """Média do pior 1% dos frames ("1% low", como em métricas de fps de jogos).

    A média pooled esconde degradação localizada: um vídeo pode ter VMAF médio
    95 e mesmo assim ter uma cena onde a compressão visivelmente quebra. É
    justamente essa cauda que uma otimização de velocidade tende a piorar
    primeiro, então ela é medida separadamente.
    """
    if not scores:
        return None
    count = max(1, int(round(len(scores) * fraction)))
    worst = sorted(scores)[:count]
    return sum(worst) / len(worst)


def _round(value, digits: int = 4):
    return round(value, digits) if isinstance(value, (int, float)) else value


def _escape_filter_path(path: str) -> str:
    r"""Escapa um caminho para uso como valor de opção dentro de um filtergraph.

    Necessário no Windows: ``C:\...\vmaf.json`` tem ``\`` (escape do ffmpeg) e
    ``:`` (separador de opções), e sem escapar o filtergraph não parseia.
    """
    return path.replace('\\', '/').replace(':', r'\:')
