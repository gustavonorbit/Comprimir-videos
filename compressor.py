"""
Módulo de compressão de vídeos usando FFmpeg.
Gerencia conversão, redimensionamento e otimização de vídeos.
"""

import os
import subprocess
import json
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Optional, Sequence, Tuple
import re

from video_filters import build_video_filter, rotated_dimensions, rotation_filter


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
    
    @staticmethod
    def _find_ffmpeg() -> str:
        """Localiza o executável do FFmpeg."""
        if os.name == 'nt':  # Windows
            names = ['ffmpeg.exe', 'ffmpeg']
        else:  # Linux, macOS
            names = ['ffmpeg']
        
        for name in names:
            result = subprocess.run(
                ['which', name] if os.name != 'nt' else ['where', name],
                capture_output=True,
                text=True
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
        """Localiza o executável do FFprobe."""
        if os.name == 'nt':  # Windows
            names = ['ffprobe.exe', 'ffprobe']
        else:  # Linux, macOS
            names = ['ffprobe']
        
        for name in names:
            result = subprocess.run(
                ['which', name] if os.name != 'nt' else ['where', name],
                capture_output=True,
                text=True
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
                timeout=5
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
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
    
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
                'stream=width,height,duration',
                '-of', 'json',
                file_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                return None
            
            data = json.loads(result.stdout)
            if not data.get('streams'):
                return None
            
            stream = data['streams'][0]
            
            # Obter duração
            duration = float(stream.get('duration', 0))
            
            return {
                'width': stream.get('width', 0),
                'height': stream.get('height', 0),
                'duration': duration,
                'file_size': os.path.getsize(file_path)
            }
        except Exception as e:
            return None
    
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
            if self._requires_segmented_export(export_segments, input_file, video_info.get('duration', 0.0)):
                segmented_tail_filters = self._concat_tail_filters(export_segments, input_file, video_info, resolution, rotation)
                cmd = self._build_segmented_command(
                    input_file,
                    output_file,
                    video_info,
                    config,
                    segmented_tail_filters,
                    remove_audio,
                    rotation,
                    temporal_blurs,
                    export_segments
                )
                progress_duration = self._segments_duration(export_segments)
            else:
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
                
                cmd.extend([
                    '-c:v', 'libx264',
                    '-crf', str(config['crf']),
                    '-preset', config['preset']
                ])
                
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
                progress_duration = video_info['duration']
            
            # Executar compressão
            self.is_running = True
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                universal_newlines=True
            )
            
            # Processar saída e extrair progresso
            self._process_output(progress_duration, progress_callback)
            
            # Aguardar conclusão
            self.process.wait()
            
            if self.process.returncode == 0:
                if os.path.exists(output_file):
                    self.is_running = False
                    return True, "Vídeo comprimido com sucesso!"
                else:
                    self.is_running = False
                    return False, "Arquivo de saída não foi criado"
            else:
                self.is_running = False
                stderr = self.process.stderr.read() if self.process.stderr else ""
                return False, f"Erro ao comprimir: {stderr[:200]}"
        
        except Exception as e:
            self.is_running = False
            return False, f"Erro: {str(e)}"

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
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
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
        config: dict,
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

        cmd.extend([
            '-filter_complex', ';'.join(graph_parts),
            '-map', '[v]',
            '-c:v', 'libx264',
            '-crf', str(config['crf']),
            '-preset', config['preset'],
        ])

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
    
    def _process_output(self, duration: float, progress_callback: Optional[Callable] = None):
        """
        Processa a saída do FFmpeg para extrair progresso.
        
        Args:
            duration: Duração total do vídeo em segundos
            progress_callback: Função para reportar progresso (0-100)
        """
        if not self.process or not progress_callback or duration <= 0:
            return
        
        try:
            for line in iter(self.process.stderr.readline, ''):
                if not line:
                    break
                
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
            pass  # Ignorar erros ao processar progresso
    
    def cancel_compression(self):
        """Cancela a compressão em andamento."""
        if self.process and self.is_running:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
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
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                universal_newlines=True
            )

            self._process_output(video_info['duration'], progress_callback)
            self.process.wait()

            if self.process.returncode == 0:
                if os.path.exists(output_file):
                    self.is_running = False
                    return True, "Áudio extraído com sucesso!"
                self.is_running = False
                return False, "Arquivo de áudio não foi criado"

            self.is_running = False
            stderr = self.process.stderr.read() if self.process.stderr else ""
            return False, f"Erro ao extrair áudio: {stderr[:200]}"

        except Exception as e:
            self.is_running = False
            return False, f"Erro: {str(e)}"
