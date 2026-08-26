"""
Módulo de compressão de vídeos usando FFmpeg.
Gerencia conversão, redimensionamento e otimização de vídeos.
"""

import logging
import os
import subprocess
import json
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Optional, Sequence, Tuple
import re

from video_filters import build_video_filter, rotated_dimensions, rotation_filter, validate_temporal_blurs
from utils import subprocess_no_window_kwargs
import encoder_caps
import encoder_policy

logger = logging.getLogger(__name__)

# Linhas de banner/build que o ffmpeg sempre imprime no topo do stderr, antes de
# qualquer erro real. Precisam ser descartadas ao extrair a causa de uma falha,
# senao a mensagem mostrada ao usuario e sempre "ffmpeg version X.Y Copyright...".
_FFMPEG_BANNER_PREFIXES = (
    "ffmpeg version",
    "built with",
    "configuration:",
    "libavutil",
    "libavcodec",
    "libavformat",
    "libavdevice",
    "libavfilter",
    "libswscale",
    "libswresample",
    "libpostproc",
    "press [q]",
    "frame=",
)


def _extract_ffmpeg_error(stderr_text: str, max_len: int = 400) -> str:
    """Extrai a mensagem de erro real do stderr do ffmpeg, descartando o banner
    de versao/build/progresso que nao explica a causa da falha."""
    lines = [line.strip() for line in (stderr_text or "").splitlines()]
    meaningful = [
        line for line in lines
        if line and not line.lower().startswith(_FFMPEG_BANNER_PREFIXES)
    ]
    if not meaningful:
        meaningful = [line for line in lines if line]
    if not meaningful:
        return "Nenhuma saída de erro foi capturada do ffmpeg."
    return " | ".join(meaningful[-5:])[:max_len]


def _bundled_binary_candidates(name: str) -> list:
    """Caminhos onde o binário embutido pode estar quando rodando via PyInstaller
    (--onedir) ou dentro de um .app, testados antes de qualquer fallback de sistema."""
    filename = f"{name}.exe" if os.name == 'nt' else name
    candidates = []

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(os.path.join(meipass, "bin", filename))

    executable_dir = os.path.dirname(os.path.abspath(sys.executable))
    candidates.append(os.path.join(executable_dir, "bin", filename))

    if getattr(sys, "frozen", False):
        # .app/Contents/MacOS/AppName -> .app/Contents/Resources/bin
        contents_dir = os.path.dirname(executable_dir)
        candidates.append(os.path.join(contents_dir, "Resources", "bin", filename))

    if not getattr(sys, "frozen", False):
        # Rodando como script: usa o binário versionado em desktop/bin, se existir.
        candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin", filename))

    return candidates


def _macos_hardware_is_arm64() -> bool:
    """True se o Mac é Apple Silicon, independente de o Python estar sob Rosetta.

    `platform.machine()` devolve 'x86_64' quando o próprio Python roda traduzido,
    então não serve para decidir se o hardware é ARM. `sysctl hw.optional.arm64`
    responde sobre a máquina, não sobre o processo.
    """
    if sys.platform != 'darwin':
        return False
    try:
        result = subprocess.run(
            ['sysctl', '-n', 'hw.optional.arm64'],
            capture_output=True, text=True, timeout=5,
            **subprocess_no_window_kwargs()
        )
    except Exception:
        return False
    return result.returncode == 0 and result.stdout.strip() == '1'


class VideoCompressor:
    """Classe responsável pela compressão de vídeos usando FFmpeg."""
    
    # Configurações de compressão por nível
    COMPRESSION_PROFILES = {
        "Alta Qualidade": {
            "crf": 18,
            "preset": "slow",
            "description": "Menos compressão, máxima fidelidade visual"
        },
        "Balanceado": {
            "crf": 23,
            "preset": "medium",
            "description": "Boa redução com boa qualidade visual"
        },
        "Compressão Forte": {
            "crf": 28,
            "preset": "medium",
            "description": "Foco em redução agressiva"
        },
        "Compressão Máxima": {
            "crf": 32,
            "preset": "fast",
            "description": "Máxima redução (verificar qualidade)"
        }
    }
    
    def __init__(self):
        """Inicializa o compressor."""
        self.ffmpeg_path = self._find_ffmpeg()
        self.ffprobe_path = self._find_ffprobe()
        self.process: Optional[subprocess.Popen] = None
        self.is_running = False
        self._cancel_requested = False
        # Plano de encode da última execução, já considerando um eventual
        # fallback. Quem quiser saber o que REALMENTE rodou (o benchmark, um
        # diagnóstico) lê daqui em vez de recalcular e arriscar divergir.
        self.last_encode_plan: Optional['encoder_policy.EncodePlan'] = None
    
    @staticmethod
    def _find_ffmpeg() -> str:
        """Localiza o executável do FFmpeg. Prioriza o binário embutido no bundle
        (PyInstaller/.app) e só cai para o FFmpeg do sistema como fallback."""
        for candidate in _bundled_binary_candidates('ffmpeg'):
            if os.path.exists(candidate) and os.access(candidate, os.X_OK):
                return candidate

        if os.name == 'nt':  # Windows
            names = ['ffmpeg.exe', 'ffmpeg']
        else:  # Linux, macOS
            names = ['ffmpeg']

        for name in names:
            result = subprocess.run(
                ['which', name] if os.name != 'nt' else ['where', name],
                capture_output=True,
                text=True,
                **subprocess_no_window_kwargs()
            )
            if result.returncode == 0:
                return result.stdout.strip().split('\n')[0]
        
        # Tenta caminhos comuns
        common_paths = [
            'ffmpeg',
            '/usr/bin/ffmpeg',
            '/usr/local/bin/ffmpeg',
            '/opt/homebrew/bin/ffmpeg',
            'C:\\ffmpeg\\bin\\ffmpeg.exe'
        ]
        
        for path in common_paths:
            if os.path.exists(path) or os.path.exists(path + '.exe'):
                return path
        
        return 'ffmpeg'  # Deixa como fallback
    
    @staticmethod
    def _find_ffprobe() -> str:
        """Localiza o executável do FFprobe. Prioriza o binário embutido no bundle
        (PyInstaller/.app) e só cai para o FFprobe do sistema como fallback."""
        for candidate in _bundled_binary_candidates('ffprobe'):
            if os.path.exists(candidate) and os.access(candidate, os.X_OK):
                return candidate

        if os.name == 'nt':  # Windows
            names = ['ffprobe.exe', 'ffprobe']
        else:  # Linux, macOS
            names = ['ffprobe']

        for name in names:
            result = subprocess.run(
                ['which', name] if os.name != 'nt' else ['where', name],
                capture_output=True,
                text=True,
                **subprocess_no_window_kwargs()
            )
            if result.returncode == 0:
                return result.stdout.strip().split('\n')[0]
        
        # Tenta caminhos comuns
        common_paths = [
            'ffprobe',
            '/usr/bin/ffprobe',
            '/usr/local/bin/ffprobe',
            '/opt/homebrew/bin/ffprobe',
            'C:\\ffmpeg\\bin\\ffprobe.exe'
        ]
        
        for path in common_paths:
            if os.path.exists(path) or os.path.exists(path + '.exe'):
                return path
        
        return 'ffprobe'  # Deixa como fallback
    
    def is_ffmpeg_available(self) -> bool:
        """Verifica se FFmpeg está acessível."""
        try:
            result = subprocess.run(
                [self.ffmpeg_path, '-version'],
                capture_output=True,
                timeout=5,
                **subprocess_no_window_kwargs()
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def is_ffprobe_available(self) -> bool:
        """Verifica se FFprobe está acessível."""
        try:
            result = subprocess.run(
                [self.ffprobe_path, '-version'],
                capture_output=True,
                timeout=5,
                **subprocess_no_window_kwargs()
            )
            return result.returncode == 0
        except Exception:
            return False

    def probe_binary_info(self) -> dict:
        """Descreve o binário de FFmpeg que este compressor vai usar.

        Serve para diagnóstico: quando um usuário reporta "não comprime", a
        primeira pergunta é *qual* ffmpeg rodou. Um binário do sistema em vez do
        embutido, uma versão velha, ou (no macOS) um binário x86_64 rodando sob
        Rosetta 2 num Mac Apple Silicon produzem sintomas bem diferentes e não
        aparecem em nenhum log hoje.

        Devolve sempre um dict; nunca levanta. Campos:
            version                 str | None  — ex. "9.0"
            arch                    list[str]   — ex. ["x86_64", "arm64"] (vazia fora do macOS)
            is_static               bool | None — None quando não dá para saber
            encoders_disponiveis    list[str]   — subconjunto de interesse, ordenado
            is_bundled              bool        — se é o binário de desktop/bin
            path, disponivel, running_under_rosetta
        """
        info = {
            'path': self.ffmpeg_path,
            'disponivel': False,
            'version': None,
            'version_full': None,
            'arch': [],
            'is_static': None,
            'encoders_disponiveis': [],
            'is_bundled': False,
            'running_under_rosetta': None,
        }

        try:
            info['is_bundled'] = any(
                os.path.exists(c) and os.path.samefile(c, self.ffmpeg_path)
                for c in _bundled_binary_candidates('ffmpeg')
            )
        except OSError:
            pass

        try:
            result = subprocess.run(
                [self.ffmpeg_path, '-hide_banner', '-version'],
                capture_output=True, text=True, timeout=15,
                **subprocess_no_window_kwargs()
            )
        except Exception as exc:
            logger.debug("probe_binary_info: falha ao executar ffmpeg: %s", exc)
            return info

        if result.returncode != 0:
            return info

        info['disponivel'] = True
        first_line = (result.stdout or '').splitlines()[:1]
        info['version_full'] = first_line[0].strip() if first_line else None
        match = re.search(r'ffmpeg version n?(\d+\.\d+(?:\.\d+)?)', result.stdout or '')
        if match:
            info['version'] = match.group(1)

        info['encoders_disponiveis'] = self._probe_encoders()

        if sys.platform == 'darwin':
            info['arch'] = self._probe_macho_archs()
            info['is_static'] = self._probe_macho_is_static()
            # Rosetta 2: binário só-Intel numa máquina Apple Silicon. O Python
            # também pode estar sob Rosetta, então compara com o hardware real.
            if info['arch']:
                info['running_under_rosetta'] = (
                    _macos_hardware_is_arm64() and 'arm64' not in info['arch']
                )

        return info

    # Conjunto reportado por probe_binary_info. Não é a lista completa de
    # encoders do build (que tem centenas): são os que o pipeline usa hoje mais
    # os de aceleração por hardware, que é o que importa saber num diagnóstico.
    _PROBED_ENCODERS = (
        'libx264', 'libx265', 'aac',
        'h264_videotoolbox', 'hevc_videotoolbox',
        'h264_nvenc', 'hevc_nvenc',
        'h264_amf', 'h264_qsv',
    )

    def _probe_encoders(self) -> list:
        """Interseção entre _PROBED_ENCODERS e o que o binário oferece."""
        try:
            result = subprocess.run(
                [self.ffmpeg_path, '-hide_banner', '-encoders'],
                capture_output=True, text=True, timeout=15,
                **subprocess_no_window_kwargs()
            )
        except Exception:
            return []
        if result.returncode != 0:
            return []

        listing = result.stdout or ''
        # As linhas têm a forma " V....D libx264   descrição". Casar a linha
        # inteira evita casar o nome dentro da descrição de outro encoder.
        found = [
            name for name in self._PROBED_ENCODERS
            if re.search(rf'^\s*\S+\s+{re.escape(name)}\s', listing, re.M)
        ]
        return sorted(found)

    def _probe_macho_archs(self) -> list:
        """Arquiteturas dentro do Mach-O, via lipo. Lista vazia se não der."""
        try:
            result = subprocess.run(
                ['lipo', '-archs', self.ffmpeg_path],
                capture_output=True, text=True, timeout=15,
                **subprocess_no_window_kwargs()
            )
        except Exception:
            return []
        return result.stdout.split() if result.returncode == 0 else []

    def _probe_macho_is_static(self) -> Optional[bool]:
        """True se o binário só depende de /usr/lib e /System.

        Essas duas existem em qualquer Mac. Dependência de qualquer outro
        caminho (típico: /usr/local/opt do Homebrew) significa que o binário
        morre com erro de dyld em máquina que não seja a de quem o compilou.
        """
        try:
            result = subprocess.run(
                ['otool', '-L', self.ffmpeg_path],
                capture_output=True, text=True, timeout=15,
                **subprocess_no_window_kwargs()
            )
        except Exception:
            return None
        if result.returncode != 0:
            return None

        for line in result.stdout.splitlines()[1:]:
            line = line.strip()
            if not line:
                continue
            lib = line.split(' (')[0].strip()
            if not (lib.startswith('/usr/lib/') or lib.startswith('/System/')):
                return False
        return True

    def log_binary_info(self) -> dict:
        """Loga uma linha resumindo o binário. Chamado no startup."""
        info = self.probe_binary_info()

        if not info['disponivel']:
            logger.warning("FFmpeg NAO disponivel em %s", info['path'])
            return info

        detalhes = [f"versao={info['version'] or '?'}"]
        detalhes.append("embutido" if info['is_bundled'] else "do sistema")
        if info['arch']:
            detalhes.append("arch=" + "+".join(info['arch']))
        if info['is_static'] is not None:
            detalhes.append("estatico" if info['is_static'] else "DINAMICO")
        logger.info("FFmpeg: %s (%s)", info['path'], ", ".join(detalhes))

        if info.get('running_under_rosetta'):
            logger.warning(
                "FFmpeg embutido nao tem build arm64 e vai rodar sob Rosetta 2 "
                "nesta maquina Apple Silicon, com perda de performance. "
                "Rode: python desktop/tools/fetch_ffmpeg.py"
            )
        if info['is_static'] is False and info['is_bundled']:
            logger.warning(
                "FFmpeg embutido depende de bibliotecas fora de /usr/lib e /System; "
                "ele vai falhar em Macs que nao tenham essas bibliotecas. "
                "Rode: python desktop/tools/fetch_ffmpeg.py"
            )

        logger.debug("FFmpeg encoders: %s", ", ".join(info['encoders_disponiveis']))
        return info

    def get_video_info(self, file_path: str) -> Optional[dict]:
        """
        Obtém informações do vídeo usando ffprobe.
        
        Args:
            file_path: Caminho completo do arquivo de vídeo
        
        Returns:
            Dicionário com informações ou None se falhar
        """
        try:
            cmd = [
                self.ffprobe_path,
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries',
                'stream=width,height,duration:stream_side_data=rotation:stream_tags=rotate',
                '-of', 'json',
                file_path
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, **subprocess_no_window_kwargs())

            if result.returncode != 0:
                return None

            data = json.loads(result.stdout)
            if not data.get('streams'):
                return None

            stream = data['streams'][0]

            # Obter duração
            duration = float(stream.get('duration', 0))

            stored_width = int(stream.get('width', 0) or 0)
            stored_height = int(stream.get('height', 0) or 0)

            # Dimensões de EXIBIÇÃO: o FFmpeg auto-rotaciona o frame conforme o
            # display matrix (rotação de metadados) tanto na prévia quanto no
            # export. Para vídeos verticais de celular (gravados 1920x1080 com
            # rotação 90°), a orientação exibida difere da armazenada. Todo o
            # cálculo de posição de blur precisa usar a orientação EXIBIDA.
            rotation = self._display_rotation(stream)
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
                'duration': duration,
                'fps': self._stream_fps(stream),
                'file_size': os.path.getsize(file_path)
            }
        except Exception:
            logger.exception("Falha ao ler informações do vídeo via ffprobe: %s", file_path)
            return None

    @staticmethod
    def _stream_fps(stream: dict) -> float:
        """Taxa de quadros como float. 0.0 se o ffprobe não souber informar.

        O ffprobe devolve uma fração ("30000/1001"), não um número. Usado pelo
        encoder_policy para dimensionar bitrate — sem fps, um vídeo 60fps
        receberia o alvo de um 30fps, ou seja, metade dos bits por quadro.
        """
        for key in ('r_frame_rate', 'avg_frame_rate'):
            raw = stream.get(key)
            if not raw or raw == '0/0':
                continue
            try:
                numerador, _, denominador = str(raw).partition('/')
                valor = float(numerador) / float(denominador or 1)
            except (TypeError, ValueError, ZeroDivisionError):
                continue
            if valor > 0:
                return valor
        return 0.0

    @staticmethod
    def _display_rotation(stream: dict) -> int:
        """Rotação de exibição (0/90/180/270) a partir do display matrix/tags.

        O FFmpeg reporta a rotação do display matrix como um ângulo que pode ser
        negativo (ex: -90). Aqui normalizamos para 0..359; apenas a paridade de
        90° importa para decidir se largura/altura são trocadas.
        """
        raw = None
        for side_data in stream.get('side_data_list', []) or []:
            if 'rotation' in side_data:
                raw = side_data.get('rotation')
                break
        if raw is None:
            raw = (stream.get('tags', {}) or {}).get('rotate')
        if raw is None:
            return 0
        try:
            angle = int(round(float(raw)))
        except (TypeError, ValueError):
            return 0
        return angle % 360
    
    def _calculate_scale_filter(self, original_info: dict, target_height: int) -> str:
        """
        Calcula o filtro de scaling mantendo proporção.
        
        Args:
            original_info: Informações do vídeo original
            target_height: Altura desejada
        
        Returns:
            String do filtro de scale do FFmpeg
        """
        if target_height == 0 or original_info['height'] == 0:
            return ""
        
        # Manter proporção: width = (original_width / original_height) * target_height
        # Usar -2 para garantir que seja par (necessário para alguns codecs)
        return f"scale=-2:{target_height}"

    def _calculate_effective_height(self, original_info: dict, rotation: int) -> int:
        """Calcula a altura do vídeo após aplicar rotação manual."""
        if rotation in (90, 270):
            return original_info.get('width', 0)
        return original_info.get('height', 0)

    def _get_rotation_filter(self, rotation: int) -> str:
        """Retorna o filtro FFmpeg para a rotação escolhida."""
        return rotation_filter(rotation)
    
    def compress_video(
        self,
        input_file: str,
        output_file: str,
        profile: str = "Balanceado",
        resolution: int = 0,  # 0 = original, 1080, 720, 480
        remove_audio: bool = False,
        rotation: int = 0,  # 0 = sem rotação, 90 = direita, 180, 270 = esquerda
        temporal_blurs: Optional[Sequence] = None,
        segments: Optional[Sequence] = None,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> Tuple[bool, str]:
        """
        Comprime um vídeo com as configurações especificadas.
        
        Args:
            input_file: Caminho do vídeo de entrada
            output_file: Caminho do vídeo de saída
            profile: Um dos COMPRESSION_PROFILES
            resolution: 0 (original), 1080, 720, 480
            remove_audio: Se True, remove áudio
            rotation: Rotação manual em graus: 0, 90, 180 ou 270
            temporal_blurs: Blurs temporais vindos do editor, aplicados por intervalo
            segments: Segmentos temporais da timeline editada
            progress_callback: Função para atualizar progresso (0-100)
        
        Returns:
            Tupla (sucesso: bool, mensagem: str)
        """
        try:
            # Validar entrada
            if not os.path.exists(input_file):
                return False, f"Arquivo não encontrado: {input_file}"
            
            if profile not in self.COMPRESSION_PROFILES:
                return False, f"Perfil inválido: {profile}"

            if rotation not in (0, 90, 180, 270):
                return False, f"Rotação inválida: {rotation}"
            
            # Obter informações do vídeo
            video_info = self.get_video_info(input_file)
            if not video_info:
                return False, "Não foi possível ler informações do vídeo"

            for warning in validate_temporal_blurs(temporal_blurs, video_info.get('width', 0), video_info.get('height', 0)):
                logger.warning(warning)

            # Preparar comando FFmpeg
            config = self.COMPRESSION_PROFILES[profile]
            
            # Iniciar valores padrão
            tail_filters = []
            
            effective_height = self._calculate_effective_height(video_info, rotation)
            if resolution > 0 and resolution != effective_height:
                scale_filter = self._calculate_scale_filter(video_info, resolution)
                if scale_filter:
                    tail_filters.append(scale_filter)

            export_segments = self._normalized_segments(segments, input_file, video_info.get('duration', 0.0))
            for segment in export_segments:
                if not os.path.exists(segment.source_path):
                    return False, f"Arquivo de segmento não encontrado: {segment.source_path}"
            use_segmented = self._requires_segmented_export(
                export_segments, input_file, video_info.get('duration', 0.0)
            )
            if use_segmented:
                segmented_tail_filters = self._concat_tail_filters(export_segments, input_file, video_info, resolution, rotation)
                progress_duration = self._segments_duration(export_segments)
            else:
                progress_duration = video_info['duration']

            def build_command(allow_hardware: bool):
                """Monta o comando completo para um plano de encode.

                É uma função, e não um comando pronto, porque o retry precisa
                montar tudo de novo com o encoder de software — os argumentos de
                hardware (`-cq`, `-q:v`, `-qp_i`...) não são intercambiáveis com
                `-crf`, então não dá para trocar só o `-c:v` no comando existente.
                """
                plan = self._encode_plan(profile, config, output_file, allow_hardware,
                                         video_info=video_info)

                if use_segmented:
                    return self._build_segmented_command(
                        input_file,
                        output_file,
                        video_info,
                        plan,
                        segmented_tail_filters,
                        remove_audio,
                        rotation,
                        temporal_blurs,
                        export_segments
                    ), plan

                cmd = [self.ffmpeg_path, '-i', input_file]
                video_filter = build_video_filter(
                    video_info.get('width', 0),
                    video_info.get('height', 0),
                    rotation=rotation,
                    temporal_blurs=temporal_blurs,
                    tail_filters=tail_filters
                )

                if video_filter:
                    cmd.extend(['-vf', video_filter])

                cmd.extend(plan.video_args)

                if remove_audio:
                    cmd.append('-an')
                else:
                    cmd.extend([
                        '-c:a', 'aac',
                        '-b:a', '128k'
                    ])

                cmd.extend([
                    '-movflags', '+faststart',
                    '-y',
                    output_file
                ])
                return cmd, plan

            cmd, plan = build_command(allow_hardware=True)

            # Executar compressão
            self.is_running = True
            self._cancel_requested = False
            returncode, stderr_output = self._run_ffmpeg(cmd, plan, progress_duration, progress_callback)

            # Encoder de hardware pode passar no probe e ainda assim falhar neste
            # vídeo específico (resolução fora do que a GPU aceita, driver que cai
            # sob carga, sessões de encode esgotadas). Refazer em software é mais
            # útil ao usuário do que devolver "falha ao exportar".
            if returncode != 0 and plan.is_hardware and not self._cancel_requested:
                logger.warning(
                    "Encoder de hardware %s falhou (returncode=%s): %s. "
                    "Refazendo a exportação com %s.",
                    plan.encoder, returncode, _extract_ffmpeg_error(stderr_output),
                    encoder_policy.SOFTWARE_ENCODER,
                )
                cmd, plan = build_command(allow_hardware=False)
                returncode, stderr_output = self._run_ffmpeg(cmd, plan, progress_duration, progress_callback)

            self.is_running = False

            if returncode == 0:
                if os.path.exists(output_file):
                    return True, "Vídeo comprimido com sucesso!"
                else:
                    logger.error("Ffmpeg retornou sucesso mas o arquivo de saída não existe: %s", output_file)
                    return False, "Arquivo de saída não foi criado"
            else:
                if self._cancel_requested:
                    logger.info("Compressão cancelada pelo usuário (stderr parcial): %s", stderr_output.strip()[-400:])
                    return False, "Compressão cancelada pelo usuário."
                error_message = _extract_ffmpeg_error(stderr_output)
                logger.error("Falha no ffmpeg (returncode=%s): %s", returncode, error_message)
                return False, f"Erro ao comprimir: {error_message}"

        except Exception as e:
            self.is_running = False
            logger.exception("Erro inesperado em compress_video.")
            return False, f"Erro: {str(e)}"

    def _encode_plan(self, profile: str, config: dict, output_file: str,
                     allow_hardware: bool = True,
                     video_info: Optional[dict] = None) -> 'encoder_policy.EncodePlan':
        """Pergunta ao policy quais argumentos de vídeo usar.

        `get_capabilities()` sem timeout **nunca** bloqueia: se o probe de
        background ainda não terminou, o retorno é `None` e o policy devolve
        software. Exportar já em libx264 é melhor do que segurar o usuário
        esperando uma detecção que só serviria para acelerar.
        """
        caps = encoder_caps.get_capabilities()
        plan = encoder_policy.plan_encode(
            profile, config, caps,
            output_file=output_file,
            video_info=video_info,
            allow_hardware=allow_hardware,
        )
        logger.info("Plano de encode: %s", plan.describe())
        self.last_encode_plan = plan
        return plan

    def _run_ffmpeg(self, cmd: list, plan: 'encoder_policy.EncodePlan',
                    progress_duration: float,
                    progress_callback: Optional[Callable] = None) -> Tuple[Optional[int], str]:
        """Roda um comando de ffmpeg até o fim. Retorna (returncode, stderr)."""
        logger.info("Iniciando ffmpeg [%s]: %s", plan.encoder, " ".join(cmd))
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            universal_newlines=True,
            **subprocess_no_window_kwargs()
        )

        # Processar saída, extrair progresso e capturar o stderr completo
        # (unica leitura possivel do stream, ver docstring de _process_output).
        stderr_output = self._process_output(progress_duration, progress_callback)

        # Aguardar conclusão
        self.process.wait()
        return self.process.returncode, stderr_output

    def _normalized_segments(self, segments: Optional[Sequence], input_file: str, duration: float) -> list:
        normalized = []
        for segment in segments or []:
            try:
                source_start = max(0.0, float(getattr(segment, "source_start")))
                source_end = max(source_start, float(getattr(segment, "source_end")))
                timeline_start = max(0.0, float(getattr(segment, "timeline_start")))
                timeline_end = max(timeline_start, float(getattr(segment, "timeline_end")))
                source_path = getattr(segment, "source_path", input_file) or input_file
                playback_rate = float(getattr(segment, "playback_rate", 1.0) or 1.0)
            except Exception:
                continue

            if source_end <= source_start or timeline_end <= timeline_start:
                continue

            normalized.append(SimpleNamespace(
                source_path=source_path,
                source_start=source_start,
                source_end=source_end,
                timeline_start=timeline_start,
                timeline_end=timeline_end,
                playback_rate=playback_rate,
            ))

        if not normalized and duration > 0:
            normalized.append(SimpleNamespace(
                source_path=input_file,
                source_start=0.0,
                source_end=float(duration),
                timeline_start=0.0,
                timeline_end=float(duration),
                playback_rate=1.0,
            ))

        return sorted(normalized, key=lambda item: item.timeline_start)

    def _concat_tail_filters(self, segments: Sequence, input_file: str, fallback_info: dict, resolution: int, rotation: int) -> list[str]:
        first_path = getattr(segments[0], "source_path", input_file) if segments else input_file
        first_info = self.get_video_info(first_path) or fallback_info
        width, height = rotated_dimensions(
            int(first_info.get('width', 0) or 0),
            int(first_info.get('height', 0) or 0),
            rotation
        )
        if width <= 0 or height <= 0:
            return []

        if resolution > 0 and resolution != height:
            target_height = resolution
            target_width = int(round(width * (target_height / height)))
        else:
            target_width = width
            target_height = height

        if target_width % 2:
            target_width += 1
        if target_height % 2:
            target_height += 1

        return [
            f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease",
            f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:color=black",
            "setsar=1",
        ]

    def _requires_segmented_export(self, segments: list, input_file: str, duration: float) -> bool:
        if len(segments) != 1:
            return bool(segments)
        segment = segments[0]
        tolerance = 0.01
        return (
            os.path.abspath(segment.source_path) != os.path.abspath(input_file)
            or abs(segment.source_start) > tolerance
            or abs(segment.source_end - float(duration or 0.0)) > tolerance
            or abs(segment.timeline_start) > tolerance
            or abs(segment.timeline_end - float(duration or 0.0)) > tolerance
            or abs(segment.playback_rate - 1.0) > tolerance
        )

    def _segments_duration(self, segments: Sequence) -> float:
        return sum(max(0.0, float(item.timeline_end) - float(item.timeline_start)) for item in segments)

    def _has_audio_stream(self, input_file: str) -> bool:
        try:
            cmd = [
                self.ffprobe_path,
                '-v', 'error',
                '-select_streams', 'a:0',
                '-show_entries', 'stream=codec_type',
                '-of', 'json',
                input_file
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, **subprocess_no_window_kwargs())
            if result.returncode != 0:
                return False
            data = json.loads(result.stdout)
            return bool(data.get('streams'))
        except Exception:
            return False

    def _build_segmented_command(
        self,
        input_file: str,
        output_file: str,
        video_info: dict,
        plan: 'encoder_policy.EncodePlan',
        tail_filters: Sequence[str],
        remove_audio: bool,
        rotation: int,
        temporal_blurs: Optional[Sequence],
        segments: Sequence,
    ) -> list[str]:
        input_paths = []
        for segment in segments:
            source_path = getattr(segment, "source_path", input_file) or input_file
            if source_path not in input_paths:
                input_paths.append(source_path)

        input_indexes = {path: index for index, path in enumerate(input_paths)}
        input_infos = {}
        audio_streams = {}
        for path in input_paths:
            input_infos[path] = self.get_video_info(path) or video_info
            audio_streams[path] = self._has_audio_stream(path)

        has_audio = (not remove_audio) and any(audio_streams.values())
        graph_parts = []
        concat_inputs = []

        for index, segment in enumerate(segments):
            source_path = getattr(segment, "source_path", input_file) or input_file
            input_index = input_indexes[source_path]
            segment_info = input_infos.get(source_path, video_info)
            source_start = max(0.0, float(segment.source_start))
            source_end = max(source_start, float(segment.source_end))
            segment_duration = max(0.0, float(segment.timeline_end) - float(segment.timeline_start))
            local_blurs = self._clip_temporal_blurs_for_segment(temporal_blurs, segment)
            for warning in validate_temporal_blurs(local_blurs, segment_info.get('width', 0), segment_info.get('height', 0)):
                logger.warning("Segmento %d (%s): %s", index, Path(source_path).name, warning)
            video_filter = build_video_filter(
                segment_info.get('width', 0),
                segment_info.get('height', 0),
                rotation=rotation,
                temporal_blurs=local_blurs,
                tail_filters=tail_filters,
                label_prefix=f"s{index}_"
            )

            video_chain = (
                f"[{input_index}:v]trim=start={source_start:.3f}:end={source_end:.3f},"
                "setpts=PTS-STARTPTS"
            )
            if abs(float(getattr(segment, "playback_rate", 1.0) or 1.0) - 1.0) > 0.01:
                rate = max(0.01, float(segment.playback_rate))
                video_chain += f",setpts=(PTS-STARTPTS)/{rate:.6f}"
            if video_filter:
                video_chain += f",{video_filter}"
            video_chain += f",format=yuv420p[v{index}]"
            graph_parts.append(video_chain)

            if has_audio:
                if audio_streams.get(source_path):
                    audio_chain = (
                        f"[{input_index}:a]atrim=start={source_start:.3f}:end={source_end:.3f},"
                        "asetpts=PTS-STARTPTS,"
                        "aresample=44100,"
                        f"aformat=sample_fmts=fltp:channel_layouts=stereo[a{index}]"
                    )
                else:
                    audio_chain = (
                        "anullsrc=channel_layout=stereo:sample_rate=44100,"
                        f"atrim=duration={segment_duration:.3f},asetpts=PTS-STARTPTS[a{index}]"
                    )
                graph_parts.append(audio_chain)
                concat_inputs.append(f"[v{index}][a{index}]")
            else:
                concat_inputs.append(f"[v{index}]")

        if has_audio:
            graph_parts.append(f"{''.join(concat_inputs)}concat=n={len(segments)}:v=1:a=1[v][a]")
        else:
            graph_parts.append(f"{''.join(concat_inputs)}concat=n={len(segments)}:v=1:a=0[v]")

        cmd = [self.ffmpeg_path]
        for path in input_paths:
            cmd.extend(['-i', path])

        cmd.extend(['-filter_complex', ';'.join(graph_parts), '-map', '[v]'])
        cmd.extend(plan.video_args)

        if has_audio:
            cmd.extend(['-map', '[a]', '-c:a', 'aac', '-b:a', '128k'])
        else:
            cmd.append('-an')

        cmd.extend(['-movflags', '+faststart', '-y', output_file])
        return cmd

    def _clip_temporal_blurs_for_segment(self, temporal_blurs: Optional[Sequence], segment) -> list:
        clipped = []
        timeline_start = float(segment.timeline_start)
        timeline_end = float(segment.timeline_end)

        for item in temporal_blurs or []:
            try:
                item_start = float(getattr(item, "start_time"))
                item_end = float(getattr(item, "end_time"))
                state = item.to_blur_state()
            except Exception:
                continue

            overlap_start = max(item_start, timeline_start)
            overlap_end = min(item_end, timeline_end)
            if overlap_end <= overlap_start:
                continue

            local_start = overlap_start - timeline_start
            local_end = overlap_end - timeline_start
            clipped.append(SimpleNamespace(
                start_time=local_start,
                end_time=local_end,
                to_blur_state=lambda state=state: state.copy(),
            ))

        return clipped
    
    def _process_output(self, duration: float, progress_callback: Optional[Callable] = None) -> str:
        """
        Le a saida de stderr do FFmpeg uma unica vez, extraindo progresso (quando
        possivel) e acumulando o texto completo para diagnostico de falhas.

        Importante: esta e a UNICA leitura de ``self.process.stderr`` por execucao.
        Uma leitura adicional depois de ``self.process.wait()`` sempre retornaria
        vazio (o stream ja estaria no EOF), o que apagava a mensagem de erro real
        em qualquer falha ocorrida durante uma compressao com progress_callback.

        Args:
            duration: Duração total do vídeo em segundos
            progress_callback: Função para reportar progresso (0-100)

        Returns:
            Texto completo (stderr) produzido pelo processo até o momento em que
            o stream foi fechado.
        """
        if not self.process or not self.process.stderr:
            return ""

        lines = []
        try:
            for line in iter(self.process.stderr.readline, ''):
                if not line:
                    break

                lines.append(line)

                if progress_callback and duration > 0:
                    # Procurar padrão de tempo: time=HH:MM:SS.ms
                    time_match = re.search(r'time=(\d+):(\d+):(\d+\.\d+)', line)
                    if time_match:
                        hours = int(time_match.group(1))
                        minutes = int(time_match.group(2))
                        seconds = float(time_match.group(3))

                        current_time = hours * 3600 + minutes * 60 + seconds
                        progress = min(100, int((current_time / duration) * 100))

                        progress_callback(progress)
        except Exception:
            logger.exception("Falha ao ler stderr do ffmpeg durante o processamento.")

        return "".join(lines)
    
    def cancel_compression(self):
        """Cancela a compressão em andamento.

        Não le stderr aqui: a thread que chamou ``compress_video``/
        ``extract_audio_mp3`` ja esta bloqueada lendo esse stream dentro de
        ``_process_output``; terminar o processo libera essa leitura, que
        entao captura e loga o stderr parcial (ver uso de ``_cancel_requested``
        em ``compress_video``).
        """
        if self.process and self.is_running:
            self._cancel_requested = True
            logger.warning("Cancelamento solicitado pelo usuário; finalizando processo ffmpeg (pid=%s).",
                            getattr(self.process, "pid", "?"))
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    logger.exception("Falha ao finalizar o processo ffmpeg após cancelamento.")
            self.is_running = False

    def extract_audio_mp3(
        self,
        input_file: str,
        output_file: str,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> Tuple[bool, str]:
        """Extrai o audio do video para MP3 mantendo o contrato usado pela UI."""
        try:
            if not os.path.exists(input_file):
                return False, f"Arquivo não encontrado: {input_file}"

            video_info = self.get_video_info(input_file)
            if not video_info:
                return False, "Não foi possível ler informações do vídeo"

            cmd = [
                self.ffmpeg_path,
                '-i', input_file,
                '-vn',
                '-codec:a', 'libmp3lame',
                '-q:a', '2',
                '-y',
                output_file
            ]

            self.is_running = True
            self._cancel_requested = False
            logger.info("Iniciando ffmpeg (extração de áudio): %s", " ".join(cmd))
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                universal_newlines=True,
                **subprocess_no_window_kwargs()
            )

            stderr_output = self._process_output(video_info['duration'], progress_callback)
            self.process.wait()

            if self.process.returncode == 0:
                if os.path.exists(output_file):
                    self.is_running = False
                    return True, "Áudio extraído com sucesso!"
                self.is_running = False
                logger.error("Ffmpeg retornou sucesso mas o arquivo de áudio não existe: %s", output_file)
                return False, "Arquivo de áudio não foi criado"

            self.is_running = False
            if self._cancel_requested:
                logger.info("Extração de áudio cancelada pelo usuário (stderr parcial): %s", stderr_output.strip()[-400:])
                return False, "Extração cancelada pelo usuário."
            error_message = _extract_ffmpeg_error(stderr_output)
            logger.error("Falha no ffmpeg ao extrair áudio (returncode=%s): %s", self.process.returncode, error_message)
            return False, f"Erro ao extrair áudio: {error_message}"

        except Exception as e:
            self.is_running = False
            logger.exception("Erro inesperado em extract_audio_mp3.")
            return False, f"Erro: {str(e)}"
