"""
Módulo de compressão de vídeos usando FFmpeg.
Gerencia conversão, redimensionamento e otimização de vídeos.
"""

import os
import subprocess
import json
import threading
from pathlib import Path
from typing import Callable, Optional, Tuple
import re


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
    
    def compress_video(
        self,
        input_file: str,
        output_file: str,
        profile: str = "Balanceado",
        resolution: int = 0,  # 0 = original, 1080, 720, 480
        remove_audio: bool = False,
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
            
            # Obter informações do vídeo
            video_info = self.get_video_info(input_file)
            if not video_info:
                return False, "Não foi possível ler informações do vídeo"
            
            # Preparar comando FFmpeg
            config = self.COMPRESSION_PROFILES[profile]
            
            # Iniciar valores padrão
            cmd = [self.ffmpeg_path, '-i', input_file]
            
            # Adicionar filtro de vídeo (scale se necessário)
            video_filters = []
            
            if resolution > 0 and resolution != video_info['height']:
                scale_filter = self._calculate_scale_filter(video_info, resolution)
                if scale_filter:
                    video_filters.append(scale_filter)
            
            if video_filters:
                cmd.extend(['-vf', ','.join(video_filters)])
            
            # Configurar codec de vídeo
            cmd.extend([
                '-c:v', 'libx264',
                '-crf', str(config['crf']),
                '-preset', config['preset']
            ])
            
            # Configurar áudio
            if remove_audio:
                cmd.append('-an')
            else:
                cmd.extend([
                    '-c:a', 'aac',
                    '-b:a', '128k'
                ])
            
            # Configurações adicionais
            cmd.extend([
                '-movflags', '+faststart',  # Permite streaming/progressivo
                '-y',  # Sobrescrever sem perguntar
                output_file
            ])
            
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
            self._process_output(video_info['duration'], progress_callback)
            
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
