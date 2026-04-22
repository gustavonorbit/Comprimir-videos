"""
Interface gráfica do programa de compressão de vídeos.
Construída com CustomTkinter para visual moderno.
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from pathlib import Path
import os
import threading
from typing import Optional
from datetime import timedelta

from compressor import VideoCompressor


class VideoCompressorGUI:
    """Interface gráfica para o compressor de vídeos."""
    
    # Cores personalizadas
    BG_COLOR = "#1a1a1a"
    FG_COLOR = "#ffffff"
    ACCENT_COLOR = "#0078d4"
    
    def __init__(self, root: ctk.CTk):
        """Inicializa a interface gráfica."""
        self.root = root
        self.compressor = VideoCompressor()
        self.compression_thread: Optional[threading.Thread] = None
        
        # Variáveis de estado
        self.input_file: Optional[str] = None
        self.output_folder: Optional[str] = None
        self.is_compressing = False
        
        # Configurar janela principal
        self.root.title("Compressor de Vídeos")
        self.root.geometry("900x750")
        self.root.resizable(True, True)
        self.root.configure(fg_color=self.BG_COLOR)
        
        # Configurar cor de destaque no sistema
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self._setup_ui()
        self._check_ffmpeg()
    
    def _setup_ui(self):
        """Configura todos os elementos da interface."""
        # Frame principal com padding
        main_frame = ctk.CTkFrame(self.root, fg_color=self.BG_COLOR)
        main_frame.pack(fill=ctk.BOTH, expand=True, padx=15, pady=15)
        
        # ===== Título =====
        title = ctk.CTkLabel(
            main_frame,
            text="🎬 Compressor de Vídeos",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=self.FG_COLOR
        )
        title.pack(pady=(0, 20))
        
        # ===== SEÇÃO 1: Seleção de Arquivo =====
        input_frame = ctk.CTkFrame(main_frame, fg_color="#262626", corner_radius=10)
        input_frame.pack(fill=ctk.X, pady=(0, 15))
        
        ctk.CTkLabel(
            input_frame,
            text="📁 ARQUIVO DE ENTRADA",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#b0b0b0"
        ).pack(anchor="w", padx=15, pady=(12, 8))
        
        # Botão selecionar arquivo
        self.btn_select_input = ctk.CTkButton(
            input_frame,
            text="Selecionar Vídeo",
            command=self._select_input_file,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=self.ACCENT_COLOR,
            hover_color="#005a9e"
        )
        self.btn_select_input.pack(padx=15, pady=(0, 10), fill=ctk.X)
        
        # Labels de informação
        self.label_input_path = ctk.CTkLabel(
            input_frame,
            text="Nenhum arquivo selecionado",
            font=ctk.CTkFont(size=10),
            text_color="#888888",
            justify="left",
            wraplength=800
        )
        self.label_input_path.pack(anchor="w", padx=15, pady=(0, 5))
        
        # Info grid
        info_grid = ctk.CTkFrame(input_frame, fg_color="transparent")
        info_grid.pack(fill=ctk.X, padx=15, pady=(0, 12))
        
        # Tamanho original
        ctk.CTkLabel(
            info_grid,
            text="Tamanho:",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#888888"
        ).pack(side=ctk.LEFT, padx=(0, 5))
        
        self.label_file_size = ctk.CTkLabel(
            info_grid,
            text="--",
            font=ctk.CTkFont(size=10),
            text_color=self.FG_COLOR
        )
        self.label_file_size.pack(side=ctk.LEFT, padx=(0, 30))
        
        # Duração
        ctk.CTkLabel(
            info_grid,
            text="Duração:",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#888888"
        ).pack(side=ctk.LEFT, padx=(0, 5))
        
        self.label_duration = ctk.CTkLabel(
            info_grid,
            text="--",
            font=ctk.CTkFont(size=10),
            text_color=self.FG_COLOR
        )
        self.label_duration.pack(side=ctk.LEFT, padx=(0, 30))
        
        # Resolução
        ctk.CTkLabel(
            info_grid,
            text="Resolução:",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#888888"
        ).pack(side=ctk.LEFT, padx=(0, 5))
        
        self.label_resolution = ctk.CTkLabel(
            info_grid,
            text="--",
            font=ctk.CTkFont(size=10),
            text_color=self.FG_COLOR
        )
        self.label_resolution.pack(side=ctk.LEFT)
        
        # ===== SEÇÃO 2: Opções de Compressão =====
        options_frame = ctk.CTkFrame(main_frame, fg_color="#262626", corner_radius=10)
        options_frame.pack(fill=ctk.X, pady=(0, 15))
        
        ctk.CTkLabel(
            options_frame,
            text="⚙️ OPÇÕES DE COMPRESSÃO",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#b0b0b0"
        ).pack(anchor="w", padx=15, pady=(12, 12))
        
        # Grid de opções
        opt_container = ctk.CTkFrame(options_frame, fg_color="transparent")
        opt_container.pack(fill=ctk.X, padx=15, pady=(0, 12))
        
        # Perfil de compressão
        ctk.CTkLabel(
            opt_container,
            text="Qualidade:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=self.FG_COLOR
        ).pack(side=ctk.LEFT, padx=(0, 10))
        
        self.combo_profile = ctk.CTkComboBox(
            opt_container,
            values=list(self.compressor.COMPRESSION_PROFILES.keys()),
            font=ctk.CTkFont(size=11),
            state="readonly"
        )
        self.combo_profile.set("Balanceado")
        self.combo_profile.pack(side=ctk.LEFT, padx=(0, 30), fill=ctk.X, expand=True)
        
        # Resolução
        ctk.CTkLabel(
            opt_container,
            text="Resolução:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=self.FG_COLOR
        ).pack(side=ctk.LEFT, padx=(0, 10))
        
        self.combo_resolution = ctk.CTkComboBox(
            opt_container,
            values=["Original", "1080p", "720p", "480p"],
            font=ctk.CTkFont(size=11),
            state="readonly"
        )
        self.combo_resolution.set("Original")
        self.combo_resolution.pack(side=ctk.LEFT, padx=(0, 30), fill=ctk.X, expand=True)
        
        # Checkbox remover áudio
        self.check_remove_audio = ctk.CTkCheckBox(
            opt_container,
            text="Remover áudio",
            font=ctk.CTkFont(size=11),
            text_color=self.FG_COLOR
        )
        self.check_remove_audio.pack(side=ctk.LEFT)
        
        # ===== SEÇÃO 3: Pasta de Saída =====
        output_frame = ctk.CTkFrame(main_frame, fg_color="#262626", corner_radius=10)
        output_frame.pack(fill=ctk.X, pady=(0, 15))
        
        ctk.CTkLabel(
            output_frame,
            text="💾 ARQUIVO DE SAÍDA",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#b0b0b0"
        ).pack(anchor="w", padx=15, pady=(12, 8))
        
        # Botão selecionar pasta
        self.btn_select_output = ctk.CTkButton(
            output_frame,
            text="Selecionar Pasta de Saída",
            command=self._select_output_folder,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=self.ACCENT_COLOR,
            hover_color="#005a9e"
        )
        self.btn_select_output.pack(padx=15, pady=(0, 10), fill=ctk.X)
        
        # Label pasta de saída
        self.label_output_path = ctk.CTkLabel(
            output_frame,
            text="Padrão: mesma pasta do arquivo",
            font=ctk.CTkFont(size=10),
            text_color="#888888",
            justify="left",
            wraplength=800
        )
        self.label_output_path.pack(anchor="w", padx=15, pady=(0, 12))
        
        # ===== BARRA DE PROGRESSO =====
        progress_frame = ctk.CTkFrame(main_frame, fg_color="#262626", corner_radius=10)
        progress_frame.pack(fill=ctk.X, pady=(0, 15))
        
        ctk.CTkLabel(
            progress_frame,
            text="⏳ PROGRESSO",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#b0b0b0"
        ).pack(anchor="w", padx=15, pady=(12, 8))
        
        self.progress_bar = ctk.CTkProgressBar(
            progress_frame,
            fg_color="#404040",
            progress_color=self.ACCENT_COLOR
        )
        self.progress_bar.set(0)
        self.progress_bar.pack(padx=15, pady=(0, 8), fill=ctk.X)
        
        self.label_progress = ctk.CTkLabel(
            progress_frame,
            text="Aguardando...",
            font=ctk.CTkFont(size=10),
            text_color="#888888"
        )
        self.label_progress.pack(anchor="w", padx=15, pady=(0, 12))
        
        # ===== BOTÕES DE AÇÃO =====
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(fill=ctk.X, pady=(0, 15))
        
        self.btn_compress = ctk.CTkButton(
            button_frame,
            text="🚀 COMPRIMIR VÍDEO",
            command=self._start_compression,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#0d7a2e",
            hover_color="#0a5b22",
            height=45
        )
        self.btn_compress.pack(side=ctk.LEFT, fill=ctk.BOTH, expand=True, padx=(0, 8))
        
        self.btn_cancel = ctk.CTkButton(
            button_frame,
            text="✕ Cancelar",
            command=self._cancel_compression,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#7a0000",
            hover_color="#5a0000",
            height=45,
            state="disabled"
        )
        self.btn_cancel.pack(side=ctk.LEFT, fill=ctk.BOTH, expand=True)
        
        # ===== ÁREA DE STATUS =====
        status_frame = ctk.CTkFrame(main_frame, fg_color="#262626", corner_radius=10)
        status_frame.pack(fill=ctk.BOTH, expand=True, pady=(0, 0))
        
        ctk.CTkLabel(
            status_frame,
            text="📊 RESULTADO",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#b0b0b0"
        ).pack(anchor="w", padx=15, pady=(12, 8))
        
        # Text widget para mostrar status
        self.status_text = ctk.CTkTextbox(
            status_frame,
            font=ctk.CTkFont(size=10),
            fg_color="#1a1a1a",
            border_color="#404040",
            border_width=1,
            text_color="#888888"
        )
        self.status_text.pack(padx=15, pady=(0, 12), fill=ctk.BOTH, expand=True)
        self.status_text.configure(state="disabled")
        
        self._add_status("Bem-vindo ao Compressor de Vídeos!")
        self._add_status("1. Selecione um arquivo de vídeo")
        self._add_status("2. Configure as opções desejadas")
        self._add_status("3. Clique em COMPRIMIR VÍDEO")
    
    def _check_ffmpeg(self):
        """Verifica se FFmpeg está disponível."""
        if not self.compressor.is_ffmpeg_available():
            messagebox.showerror(
                "FFmpeg não encontrado",
                "FFmpeg não está instalado ou não foi encontrado.\n\n"
                "Instale FFmpeg por favor.\n\n"
                "macOS (Homebrew):\nbrew install ffmpeg\n\n"
                "Windows (Chocolatey):\nchoco install ffmpeg\n\n"
                "Linux (Ubuntu/Debian):\nsudo apt install ffmpeg"
            )
            self._add_status("❌ ERRO: FFmpeg não foi encontrado!")
    
    def _prepare_window_for_dialog(self):
        """
        Prepara a janela principal para abrir um diálogo nativo.
        Solução para macOS: garante que a janela esteja em foco.
        """
        try:
            self.root.lift()
            self.root.focus_force()
            self.root.update_idletasks()
        except Exception:
            pass  # Ignorar erros de lift/focus
    
    def _open_file_dialog(self, title: str, filetypes: tuple) -> Optional[str]:
        """
        Abre um diálogo de seleção de arquivo de forma robusta.
        
        Solução para macOS: 
        - Associa o diálogo à janela principal com parent
        - Prepara a janela antes de abrir o diálogo
        - Executa na thread principal
        
        Args:
            title: Título do diálogo
            filetypes: Tupla de tipos de arquivo ((label, pattern), ...)
        
        Returns:
            Caminho do arquivo ou None se cancelado
        """
        self._prepare_window_for_dialog()
        
        try:
            file_path = filedialog.askopenfilename(
                parent=self.root,
                title=title,
                filetypes=filetypes
            )
            return file_path if file_path else None
        except Exception as e:
            self._add_status(f"❌ Erro ao abrir diálogo de arquivo: {str(e)}")
            return None
    
    def _open_directory_dialog(self, title: str) -> Optional[str]:
        """
        Abre um diálogo de seleção de pasta de forma robusta.
        
        Solução para macOS:
        - Associa o diálogo à janela principal com parent
        - Prepara a janela antes de abrir o diálogo
        - Executa na thread principal
        
        Args:
            title: Título do diálogo
        
        Returns:
            Caminho da pasta ou None se cancelado
        """
        self._prepare_window_for_dialog()
        
        try:
            folder = filedialog.askdirectory(
                parent=self.root,
                title=title
            )
            return folder if folder else None
        except Exception as e:
            self._add_status(f"❌ Erro ao abrir diálogo de pasta: {str(e)}")
            return None
    
    def _select_input_file(self):
        """Abre diálogo para selecionar arquivo de vídeo."""
        video_formats = (
            ("Arquivos de Vídeo (*.mp4 *.mov *.mkv *.avi *.wmv *.flv *.webm *.m4v *.mpeg *.mpg *.3gp *.ts *.mts *.m2ts)", 
             "*.mp4 *.mov *.mkv *.avi *.wmv *.flv *.webm *.m4v *.mpeg *.mpg *.3gp *.ts *.mts *.m2ts"),
            ("Todos os arquivos", "*.*")
        )
        
        file_path = self._open_file_dialog(
            title="Selecione um arquivo de vídeo",
            filetypes=video_formats
        )
        
        if not file_path:
            return
        
        self.input_file = file_path
        self._update_input_info()
    
    def _update_input_info(self):
        """Atualiza as informações do arquivo selecionado."""
        if not self.input_file:
            return
        
        # Atualizar caminho
        file_name = Path(self.input_file).name
        self.label_input_path.configure(text=f"📄 {file_name}\n{self.input_file}")
        
        # Obter informações
        info = self.compressor.get_video_info(self.input_file)
        
        if info:
            # Tamanho do arquivo
            size_mb = info['file_size'] / (1024 * 1024)
            self.label_file_size.configure(text=f"{size_mb:.2f} MB")
            
            # Duração
            duration_str = str(timedelta(seconds=int(info['duration'])))
            self.label_duration.configure(text=duration_str)
            
            # Resolução
            resolution_str = f"{info['width']}x{info['height']}"
            self.label_resolution.configure(text=resolution_str)
            
            self._add_status(f"✅ Arquivo carregado: {file_name} ({size_mb:.2f} MB)")
        else:
            messagebox.showerror(
                "Erro",
                "Não foi possível ler as informações do vídeo.\n"
                "Verifique se o arquivo é válido."
            )
            self.input_file = None
            self.label_input_path.configure(text="Erro ao ler arquivo")
    
    def _select_output_folder(self):
        """Abre diálogo para selecionar pasta de saída."""
        folder = self._open_directory_dialog(
            title="Selecione a pasta de saída"
        )
        
        if folder:
            self.output_folder = folder
            folder_name = Path(folder).name or folder
            self.label_output_path.configure(text=f"📁 {folder}")
            self._add_status(f"✅ Pasta de saída definida: {folder_name}")
    
    def _start_compression(self):
        """Inicia o processo de compressão."""
        # Validações
        if not self.input_file:
            messagebox.showwarning("Erro", "Por favor, selecione um arquivo de vídeo.")
            return
        
        if not self.compressor.is_ffmpeg_available():
            messagebox.showerror(
                "Erro",
                "FFmpeg não está acessível. Verifique a instalação."
            )
            return
        
        # Preparar caminho de saída
        output_folder = self.output_folder or str(Path(self.input_file).parent)
        
        if not os.path.isdir(output_folder):
            messagebox.showerror("Erro", "Pasta de saída inválida.")
            return
        
        # Gerar nome do arquivo de saída
        input_name = Path(self.input_file).stem
        output_file = os.path.join(output_folder, f"{input_name}_comprimido.mp4")
        
        # Verificar se arquivo já existe
        if os.path.exists(output_file):
            response = messagebox.askyesno(
                "Arquivo Existe",
                f"O arquivo {Path(output_file).name} já existe.\nDeseja sobrescrever?"
            )
            if not response:
                return
        
        # Desabilitar botões
        self.btn_compress.configure(state="disabled")
        self.btn_cancel.configure(state="normal")
        self.btn_select_input.configure(state="disabled")
        self.btn_select_output.configure(state="disabled")
        self.is_compressing = True
        
        # Iniciar thread de compressão
        self.compression_thread = threading.Thread(
            target=self._compression_worker,
            args=(output_file,),
            daemon=True
        )
        self.compression_thread.start()
    
    def _compression_worker(self, output_file: str):
        """Thread worker para compressão."""
        try:
            profile = self.combo_profile.get()
            resolution_text = self.combo_resolution.get()
            remove_audio = self.check_remove_audio.get()
            
            # Converter resolução
            resolution_map = {
                "Original": 0,
                "1080p": 1080,
                "720p": 720,
                "480p": 480
            }
            resolution = resolution_map.get(resolution_text, 0)
            
            self._add_status(f"🔄 Iniciando compressão com perfil '{profile}'...")
            
            success, message = self.compressor.compress_video(
                self.input_file,
                output_file,
                profile=profile,
                resolution=resolution,
                remove_audio=remove_audio,
                progress_callback=self._update_progress
            )
            
            if success:
                self._show_results(output_file)
            else:
                self._add_status(f"❌ Erro: {message}")
                messagebox.showerror("Erro na Compressão", message)
        
        except Exception as e:
            self._add_status(f"❌ Exceção: {str(e)}")
            messagebox.showerror("Erro", f"Erro inesperado: {str(e)}")
        
        finally:
            self.is_compressing = False
            self.root.after(0, self._compression_finished)
    
    def _update_progress(self, progress: int):
        """Atualiza a barra de progresso."""
        self.root.after(
            0,
            lambda: self._update_progress_ui(progress)
        )
    
    def _update_progress_ui(self, progress: int):
        """Atualiza a UI de progresso."""
        self.progress_bar.set(progress / 100)
        self.label_progress.configure(text=f"Progresso: {progress}%")
    
    def _show_results(self, output_file: str):
        """Mostra os resultados da compressão."""
        try:
            input_size = os.path.getsize(self.input_file)
            output_size = os.path.getsize(output_file)
            reduction_percent = ((input_size - output_size) / input_size) * 100
            
            input_mb = input_size / (1024 * 1024)
            output_mb = output_size / (1024 * 1024)
            
            self._add_status("=" * 60)
            self._add_status("✅ COMPRESSÃO CONCLUÍDA COM SUCESSO!")
            self._add_status("=" * 60)
            self._add_status(f"📊 Tamanho Original: {input_mb:.2f} MB")
            self._add_status(f"📊 Tamanho Final: {output_mb:.2f} MB")
            self._add_status(f"📊 Redução: {reduction_percent:.1f}%")
            self._add_status(f"💾 Arquivo salvo em: {output_file}")
            self._add_status("=" * 60)
            
            # Oferecer para abrir pasta
            response = messagebox.showinfo(
                "Sucesso!",
                f"Vídeo comprimido com sucesso!\n\n"
                f"Tamanho Original: {input_mb:.2f} MB\n"
                f"Tamanho Final: {output_mb:.2f} MB\n"
                f"Redução: {reduction_percent:.1f}%\n\n"
                f"Clique OK para abrir a pasta."
            )
            
            if response == "ok":
                self._open_output_folder(output_file)
        
        except Exception as e:
            self._add_status(f"❌ Erro ao obter informações: {str(e)}")
    
    def _open_output_folder(self, file_path: str):
        """Abre a pasta contendo o arquivo."""
        try:
            folder = os.path.dirname(file_path)
            if os.name == 'nt':  # Windows
                os.startfile(folder)
            elif os.name == 'posix':  # macOS/Linux
                os.system(f'open "{folder}"')
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível abrir a pasta: {str(e)}")
    
    def _cancel_compression(self):
        """Cancela a compressão em andamento."""
        if messagebox.askyesno("Cancelar", "Deseja realmente cancelar a compressão?"):
            self.compressor.cancel_compression()
            self._add_status("⚠️ Compressão cancelada pelo usuário")
            self._compression_finished()
    
    def _compression_finished(self):
        """Chamado quando a compressão termina (com sucesso ou erro)."""
        self.btn_compress.configure(state="normal")
        self.btn_cancel.configure(state="disabled")
        self.btn_select_input.configure(state="normal")
        self.btn_select_output.configure(state="normal")
        self.progress_bar.set(0)
        self.label_progress.configure(text="Aguardando...")
    
    def _add_status(self, message: str):
        """Adiciona uma mensagem à área de status."""
        self.status_text.configure(state="normal")
        self.status_text.insert(ctk.END, message + "\n")
        self.status_text.see(ctk.END)
        self.status_text.configure(state="disabled")
        self.root.update_idletasks()
