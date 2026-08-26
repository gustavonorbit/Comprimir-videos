"""
Ponto de entrada do Compressor de Vídeos.
Inicializa a aplicação e a interface gráfica.
"""

import logging
import logging.handlers
import platform
import sys
import os
import customtkinter as ctk

# Adicionar diretório atual ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from compressor import VideoCompressor
from ui import VideoCompressorGUI
import encoder_caps

APP_NAME = "Project Codename"


def _user_log_dir() -> str:
    """Pasta de logs do usuário, seguindo a convenção de cada SO."""
    home = os.path.expanduser("~")
    system = platform.system()
    if system == "Darwin":
        return os.path.join(home, "Library", "Logs", APP_NAME)
    if system == "Windows":
        base = os.environ.get("LOCALAPPDATA") or os.path.join(home, "AppData", "Local")
        return os.path.join(base, APP_NAME, "logs")
    return os.path.join(home, ".local", "state", APP_NAME, "logs")


def setup_logging() -> None:
    """Configura logging INFO+ com rotação em arquivo, para que os
    logger.warning/error/exception já inseridos no compressor, nos filtros de
    vídeo e na UI fiquem persistidos e diagnosticáveis pelo suporte, sem
    depender do usuário estar com o terminal aberto."""
    log_dir = _user_log_dir()
    try:
        os.makedirs(log_dir, exist_ok=True)
    except OSError:
        log_dir = None

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    if log_dir:
        handler = logging.handlers.RotatingFileHandler(
            os.path.join(log_dir, "app.log"),
            maxBytes=2_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s"
        ))
        root_logger.addHandler(handler)


def main():
    """Função principal da aplicação."""
    setup_logging()
    logger = logging.getLogger(__name__)

    # Registra qual ffmpeg foi resolvido antes de qualquer compressão. Sem isso,
    # um relato de "não comprime" não diz se rodou o binário embutido ou o do
    # sistema, nem se está sob Rosetta 2 — e é o primeiro dado necessário.
    try:
        compressor = VideoCompressor()
        compressor.log_binary_info()
        # Detecção de encoders de hardware: roda numa thread daemon e não
        # bloqueia nada. Até terminar, as exportações usam software — o custo de
        # esperar seria pago pelo usuário, o de não esperar é só perder
        # aceleração nos primeiros segundos de uso.
        encoder_caps.start_background_detection(compressor.ffmpeg_path)
    except Exception:
        logger.exception("Falha ao inspecionar o binário do FFmpeg no startup.")

    try:
        # Criar janela principal
        root = ctk.CTk()

        # Criar interface gráfica
        app = VideoCompressorGUI(root)

        # Iniciar loop da aplicação
        root.mainloop()

    except Exception as e:
        logger.exception("Erro ao iniciar a aplicação.")
        print(f"Erro ao iniciar a aplicação: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
