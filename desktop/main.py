"""
Ponto de entrada do Compressor de Vídeos.
Inicializa a aplicação e a interface gráfica.
"""

import sys
import os
import customtkinter as ctk

# Adicionar diretório atual ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui import VideoCompressorGUI


def main():
    """Função principal da aplicação."""
    try:
        # Criar janela principal
        root = ctk.CTk()
        
        # Criar interface gráfica
        app = VideoCompressorGUI(root)
        
        # Iniciar loop da aplicação
        root.mainloop()
    
    except Exception as e:
        print(f"Erro ao iniciar a aplicação: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
