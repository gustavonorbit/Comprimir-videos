"""
Funções utilitárias para o compressor de vídeos.
"""

import os
import platform
import subprocess
import sys
from typing import Tuple


def subprocess_no_window_kwargs() -> dict:
    """kwargs para chamadas de subprocess que evitam abrir uma janela de console.

    Somente no Windows: como o app é empacotado como GUI (``console=False``), cada
    processo externo (ffmpeg/ffprobe) abriria uma janela de terminal ao ser
    disparado. Aqui suprimimos essa janela com ``CREATE_NO_WINDOW`` + ``SW_HIDE``.

    Em macOS/Linux retorna ``{}`` — nenhum efeito, comportamento inalterado.
    """
    if sys.platform != "win32":
        return {}

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return {
        "creationflags": subprocess.CREATE_NO_WINDOW,
        "startupinfo": startupinfo,
    }


def format_file_size(bytes_size: int) -> str:
    """
    Formata tamanho de arquivo em forma legível.
    
    Args:
        bytes_size: Tamanho em bytes
    
    Returns:
        String formatada (ex: "123.45 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} TB"


def format_duration(seconds: float) -> str:
    """
    Formata duração em forma legível.
    
    Args:
        seconds: Duração em segundos
    
    Returns:
        String formatada (ex: "1:23:45")
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"


def get_system_info() -> dict:
    """
    Obtém informações do sistema.
    
    Returns:
        Dict com informações do SO
    """
    return {
        'system': platform.system(),
        'release': platform.release(),
        'processor': platform.processor(),
        'python_version': platform.python_version()
    }


def open_folder_in_explorer(folder_path: str) -> bool:
    """
    Abre uma pasta no explorador/finder do sistema operacional.
    
    Args:
        folder_path: Caminho da pasta
    
    Returns:
        True se bem-sucedido, False caso contrário
    """
    try:
        system = platform.system()
        
        if system == 'Darwin':  # macOS
            subprocess.Popen(['open', folder_path])
            return True
        elif system == 'Windows':
            os.startfile(folder_path)
            return True
        elif system == 'Linux':
            subprocess.Popen(['xdg-open', folder_path])
            return True
        else:
            return False
    except Exception:
        return False


def estimate_output_size(
    input_size: int,
    profile: str,
    has_audio: bool = True,
    resolution_reduction: float = 1.0
) -> Tuple[int, float]:
    """
    Estima o tamanho do arquivo após compressão.
    
    Este é um cálculo heurístico baseado em compressão típica.
    
    Args:
        input_size: Tamanho original em bytes
        profile: Um dos perfis de compressão
        has_audio: Se o arquivo terá áudio
        resolution_reduction: Fator de redução de resolução (1.0 = original)
    
    Returns:
        Tupla (tamanho_estimado_bytes, taxa_compressão)
    """
    # Fatores de compressão típicos por perfil (em relação ao original)
    compression_factors = {
        "Alta Qualidade": 0.65,
        "Balanceado": 0.40,
        "Compressão Forte": 0.25,
        "Compressão Máxima": 0.15
    }
    
    factor = compression_factors.get(profile, 0.40)
    
    # Ajustar por redução de resolução (area = width * height)
    # Redução de área é ~quadrática
    resolution_factor = resolution_reduction ** 2
    
    # Se remover áudio, economiza cerca de 5-15% tipicamente
    audio_factor = 1.0 if has_audio else 0.90
    
    # Cálculo final
    estimated_size = int(input_size * factor * resolution_factor * audio_factor)
    compression_ratio = (input_size - estimated_size) / input_size * 100 if input_size > 0 else 0
    
    return estimated_size, compression_ratio


def validate_ffmpeg_installation() -> Tuple[bool, str]:
    """
    Valida se FFmpeg está instalado e funcional.
    
    Returns:
        Tupla (está_instalado: bool, mensagem: str)
    """
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            timeout=5,
            **subprocess_no_window_kwargs()
        )
        if result.returncode == 0:
            # Extrair versão
            output = result.stdout.decode('utf-8', errors='ignore')
            version_line = output.split('\n')[0]
            return True, f"FFmpeg instalado: {version_line}"
        else:
            return False, "FFmpeg encontrado mas não funciona corretamente"
    except FileNotFoundError:
        return False, "FFmpeg não foi encontrado no PATH"
    except subprocess.TimeoutExpired:
        return False, "FFmpeg não respondeu a tempo"
    except Exception as e:
        return False, f"Erro ao verificar FFmpeg: {str(e)}"
