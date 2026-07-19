"""
Interface gráfica do programa de compressão de vídeos.
Construída com CustomTkinter para visual moderno.
"""

import json
import os
import platform
import subprocess
import tkinter as tk
import threading
import time
from datetime import timedelta
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Optional

import customtkinter as ctk

from blur_state import NormalizedRect
from compressor import VideoCompressor
from editor_state import DEFAULT_PRIVACY_BLUR_STRENGTH, BlurFilter, EditorState
from editor_timeline import EditorTimeline
from video_preview import VideoPreview


class Tooltip:
    """Tooltip simples e leve para widgets Tk/CustomTkinter."""

    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.after_id = None

        widget.bind("<Enter>", self._schedule)
        widget.bind("<Leave>", self._hide)
        widget.bind("<ButtonPress>", self._hide)

    def set_text(self, text: str):
        self.text = text

    def _schedule(self, _event=None):
        self._cancel()
        self.after_id = self.widget.after(450, self._show)

    def _show(self):
        self.after_id = None
        if self.tip_window or not self.text:
            return

        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        self.tip_window = tk.Toplevel(self.widget)
        self.tip_window.wm_overrideredirect(True)
        self.tip_window.wm_geometry(f"+{x}+{y}")

        label = tk.Label(
            self.tip_window,
            text=self.text,
            background="#111827",
            foreground="#FFFFFF",
            relief="solid",
            borderwidth=0,
            padx=8,
            pady=5,
            font=("Arial", 11)
        )
        label.pack()

    def _hide(self, _event=None):
        self._cancel()
        if self.tip_window:
            try:
                self.tip_window.destroy()
            except Exception:
                pass
            self.tip_window = None

    def _cancel(self):
        if self.after_id is not None:
            try:
                self.widget.after_cancel(self.after_id)
            except Exception:
                pass
            self.after_id = None


class VideoCompressorGUI:
    """Interface gráfica para o compressor de vídeos."""

    INITIAL_SIZE = (940, 720)
    MIN_SIZE = (900, 700)

    BG_COLOR = "#F7F7F8"
    CARD_COLOR = "#FFFFFF"
    SURFACE_COLOR = "#F8FAFC"
    TEXT_COLOR = "#111827"
    MUTED_COLOR = "#667085"
    SUBTLE_TEXT_COLOR = "#98A2B3"
    BORDER_COLOR = "#E4E9F1"
    STRONG_BORDER_COLOR = "#D5DDEC"
    ACCENT_COLOR = "#007AFF"
    ACCENT_HOVER_COLOR = "#0066D6"
    ACCENT_SOFT_COLOR = "#EAF4FF"
    SUCCESS_COLOR = "#34C759"
    DANGER_COLOR = "#FF3B30"
    DANGER_SOFT_COLOR = "#FFF2F1"
    DISABLED_COLOR = "#B8C0CC"

    def __init__(self, root: ctk.CTk):
        """Inicializa a interface gráfica."""
        self.root = root
        self.compressor = VideoCompressor()
        self.compression_thread: Optional[threading.Thread] = None
        self.ui_thread = threading.current_thread()

        self.input_file: Optional[str] = None
        self.rotation_degrees = 0
        self.remove_audio = False
        self.editor_state = EditorState()
        self._syncing_time = False
        self._pending_timeline_blur_start: Optional[float] = None
        self._playback_tick_after_id = None
        self._playback_tick_started_at = 0.0
        self._playback_tick_base_time = 0.0
        self._last_active_filter_ids: set[str] = set()
        self.processing_blur_enabled = False
        self.processing_temporal_blurs = []
        self.processing_segments = []
        self.is_compressing = False
        self.processing_started_at: Optional[float] = None
        self.last_operation_succeeded = False
        self.last_output_file: Optional[str] = None
        self.last_status_message: Optional[str] = None
        self.status_messages: list[str] = []
        self.processing_terminal_message: Optional[str] = None
        self._resize_after_id = None
        self._is_expanded_layout = False
        self._options_wrapped: Optional[bool] = None

        self.font_family = self._detect_font_family()

        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        self._configure_window()
        self._setup_ui()
        self._check_ffmpeg()

    def _detect_font_family(self) -> str:
        """Escolhe uma família próxima ao padrão Apple, com fallback leve."""
        try:
            if self.root.tk.call("tk", "windowingsystem") == "aqua":
                return "SF Pro Display"
        except Exception:
            pass
        return "Inter"

    def _font(self, size: int, weight: Optional[str] = None) -> ctk.CTkFont:
        return ctk.CTkFont(family=self.font_family, size=size, weight=weight)

    def _configure_window(self):
        """Configura tamanho compacto inicial, centralização e mínimo seguro."""
        width, height = self.INITIAL_SIZE

        self.root.title("Compressor de Vídeos")
        self.root.configure(fg_color=self.BG_COLOR)
        self.root.resizable(True, True)
        self.root.minsize(*self.MIN_SIZE)

        try:
            self.root.state("normal")
        except Exception:
            pass

        try:
            self.root.attributes("-fullscreen", False)
        except Exception:
            pass

        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = max(0, int((screen_width - width) / 2))
        y = max(0, int((screen_height - height) / 2))
        self.root.geometry(f"{width}x{height}+{x}+{y}")

        self.root.bind("<Configure>", self._on_window_configure)
        self.root.bind("<Command-r>", self._rotation_shortcut)
        self.root.bind("<Control-r>", self._rotation_shortcut)
        self.root.bind("<Command-m>", self._audio_shortcut)
        self.root.bind("<Control-m>", self._audio_shortcut)
        self.root.bind("<Command-b>", self._split_shortcut)
        self.root.bind("<Control-b>", self._split_shortcut)
        self.root.bind("<Command-z>", self._undo_shortcut)
        self.root.bind("<Control-z>", self._undo_shortcut)
        self.root.bind("<Command-Shift-Z>", self._redo_shortcut)
        self.root.bind("<Control-Shift-Z>", self._redo_shortcut)
        self.root.bind("<Control-y>", self._redo_shortcut)
        self.root.bind("<Delete>", self._delete_timeline_shortcut)
        self.root.bind("<BackSpace>", self._delete_timeline_shortcut)
        self.root.bind("<Escape>", self._cancel_blur_selection_shortcut)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_window_configure(self, event=None):
        if event is not None and event.widget is not self.root:
            return

        if self._resize_after_id is not None:
            try:
                self.root.after_cancel(self._resize_after_id)
            except Exception:
                pass

        self._resize_after_id = self.root.after(120, self._apply_responsive_mode)

    def _apply_responsive_mode(self):
        self._resize_after_id = None
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        expanded = width >= 1180 or height >= 840

        if expanded == self._is_expanded_layout:
            self._layout_options_bar(self._should_wrap_options())
            return

        self._is_expanded_layout = expanded
        padx = 24 if expanded else 18
        pady = 20 if expanded else 16
        column_gap = 16 if expanded else 12

        self.main_frame.pack_configure(padx=padx, pady=pady)
        self.left_column.grid_configure(padx=(0, column_gap))
        self._layout_options_bar(self._should_wrap_options())

    def _should_wrap_options(self) -> bool:
        if not hasattr(self, "options_content"):
            return False

        self.options_content.update_idletasks()
        return self.options_content.winfo_width() < 900

    def _on_close(self):
        self._cancel_playback_tick()
        try:
            self.video_preview.release()
        except Exception:
            pass

        if self.is_compressing:
            try:
                self.compressor.cancel_compression()
            except Exception:
                pass

        self.root.destroy()

    def _create_card(self, parent, corner_radius: int = 14) -> ctk.CTkFrame:
        return ctk.CTkFrame(
            parent,
            fg_color=self.CARD_COLOR,
            corner_radius=corner_radius,
            border_width=1,
            border_color=self.BORDER_COLOR
        )

    def _create_combo(self, parent, values, width: int = 160) -> ctk.CTkComboBox:
        return ctk.CTkComboBox(
            parent,
            values=values,
            font=self._font(12),
            dropdown_font=self._font(12),
            state="readonly",
            width=width,
            height=36,
            corner_radius=10,
            fg_color="#FFFFFF",
            text_color=self.TEXT_COLOR,
            border_color=self.STRONG_BORDER_COLOR,
            border_width=1,
            button_color="#EEF3F9",
            button_hover_color="#E2EAF5",
            dropdown_fg_color="#FFFFFF",
            dropdown_hover_color=self.ACCENT_SOFT_COLOR,
            dropdown_text_color=self.TEXT_COLOR
        )

    def _create_secondary_button(self, parent, text: str, command, height: int = 38) -> ctk.CTkButton:
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            font=self._font(12, "bold"),
            height=height,
            corner_radius=10,
            fg_color="#FFFFFF",
            hover_color="#F2F6FB",
            text_color=self.TEXT_COLOR,
            border_width=1,
            border_color=self.STRONG_BORDER_COLOR
        )

    def _section_label(self, parent, text: str, row: int, column: int = 0, columnspan: int = 1):
        ctk.CTkLabel(
            parent,
            text=text,
            font=self._font(15, "bold"),
            text_color=self.TEXT_COLOR,
            anchor="w"
        ).grid(row=row, column=column, columnspan=columnspan, sticky="w")

    def _setup_ui(self):
        """Configura todos os elementos da interface."""
        self.main_frame = ctk.CTkFrame(self.root, fg_color=self.BG_COLOR)
        self.main_frame.pack(fill=ctk.BOTH, expand=True, padx=18, pady=16)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1)

        self._build_header(self.main_frame)
        self._build_main_area(self.main_frame)

        self._add_status("Bem-vindo ao Compressor de Vídeos.")
        self._add_status("Selecione um vídeo, ajuste as opções e inicie o processamento.")
        self._initialize_static_visual_state()

    def _initialize_static_visual_state(self):
        self._set_metadata_placeholders()
        self._layout_options_bar(True)
        self._update_split_button_state()
        self.root.after_idle(self._apply_initial_layout)

    def _apply_initial_layout(self):
        self._set_metadata_placeholders()
        self._layout_options_bar(self._should_wrap_options())
        self._update_split_button_state()
        self.root.update_idletasks()

    def _set_metadata_placeholders(self):
        if not hasattr(self, "label_file_size"):
            return

        self.label_file_size.configure(text="--")
        self.label_duration.configure(text="--")
        self.label_resolution.configure(text="--")
        self.label_codec.configure(text="--")

    def _build_header(self, parent):
        header = ctk.CTkFrame(parent, fg_color="transparent", height=62)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        header.grid_propagate(False)
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="Compressor de Vídeos",
            font=self._font(27, "bold"),
            text_color=self.TEXT_COLOR,
            anchor="w"
        ).grid(row=0, column=0, sticky="w", pady=(2, 0))

        ctk.CTkLabel(
            header,
            text="Prepare vídeos menores com qualidade e controle em poucos cliques.",
            font=self._font(13),
            text_color=self.MUTED_COLOR,
            anchor="w"
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))

    def _build_main_area(self, parent):
        self.body = ctk.CTkFrame(parent, fg_color="transparent")
        self.body.grid(row=1, column=0, sticky="nsew")
        self.body.grid_columnconfigure(0, weight=3, uniform="body", minsize=500)
        self.body.grid_columnconfigure(1, weight=2, uniform="body", minsize=340)
        self.body.grid_rowconfigure(0, weight=1)

        self.left_column = ctk.CTkFrame(self.body, fg_color="transparent")
        self.left_column.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self.left_column.grid_columnconfigure(0, weight=1)
        self.left_column.grid_rowconfigure(1, weight=1, minsize=260)

        self.right_column = ctk.CTkFrame(self.body, fg_color="transparent")
        self.right_column.grid(row=0, column=1, sticky="nsew")
        self.right_column.grid_columnconfigure(0, weight=1)
        self.right_column.grid_rowconfigure(2, weight=1, minsize=340)

        self._build_input_card(self.left_column)
        self._build_editor_workspace(self.left_column)

        self._build_progress_card(self.right_column)
        self._build_action_area(self.right_column)
        self._build_preview_card(self.right_column)

    def _build_input_card(self, parent):
        card = self._create_card(parent)
        card.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        card.grid_columnconfigure(0, weight=1)

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.grid(row=0, column=0, sticky="ew", padx=16, pady=15)
        content.grid_columnconfigure(0, weight=1)

        self.drop_zone = ctk.CTkFrame(
            content,
            fg_color=self.SURFACE_COLOR,
            corner_radius=13,
            border_width=1,
            border_color=self.STRONG_BORDER_COLOR,
            height=108
        )
        self.drop_zone.grid(row=0, column=0, sticky="ew")
        self.drop_zone.grid_propagate(False)
        self.drop_zone.grid_columnconfigure(1, weight=1)
        self.drop_zone.grid_columnconfigure(2, weight=0)
        self.drop_zone.grid_columnconfigure(3, weight=0)

        icon_wrap = ctk.CTkFrame(
            self.drop_zone,
            fg_color=self.ACCENT_SOFT_COLOR,
            corner_radius=14,
            width=42,
            height=42
        )
        icon_wrap.grid(row=0, column=0, rowspan=2, sticky="w", padx=(14, 12), pady=20)
        icon_wrap.grid_propagate(False)

        icon_label = ctk.CTkLabel(
            icon_wrap,
            text="+",
            font=self._font(24, "bold"),
            text_color=self.ACCENT_COLOR
        )
        icon_label.place(relx=0.5, rely=0.46, anchor="center")

        self.label_file_name = ctk.CTkLabel(
            self.drop_zone,
            text="Selecione ou arraste um vídeo",
            font=self._font(16, "bold"),
            text_color=self.TEXT_COLOR,
            anchor="w"
        )
        self.label_file_name.grid(row=0, column=1, sticky="ew", pady=(22, 0))

        self.label_input_path = ctk.CTkLabel(
            self.drop_zone,
            text="MP4, MOV, MKV, AVI, WEBM e M4V",
            font=self._font(11),
            text_color=self.MUTED_COLOR,
            anchor="w"
        )
        self.label_input_path.grid(row=1, column=1, sticky="ew", pady=(3, 20))

        self.btn_select_input = ctk.CTkButton(
            self.drop_zone,
            text="Selecionar vídeo",
            command=self._select_input_file,
            font=self._font(12, "bold"),
            width=126,
            height=36,
            corner_radius=10,
            fg_color=self.ACCENT_COLOR,
            hover_color=self.ACCENT_HOVER_COLOR,
            text_color="#FFFFFF"
        )
        self.btn_select_input.grid(row=0, column=2, rowspan=2, sticky="e", padx=(12, 8))

        self.btn_add_input = ctk.CTkButton(
            self.drop_zone,
            text="Adicionar",
            command=self._add_input_files_dialog,
            font=self._font(12, "bold"),
            width=98,
            height=36,
            corner_radius=10,
            fg_color="#FFFFFF",
            hover_color="#F2F6FB",
            text_color=self.TEXT_COLOR,
            border_width=1,
            border_color=self.STRONG_BORDER_COLOR
        )
        self.btn_add_input.grid(row=0, column=3, rowspan=2, sticky="e", padx=(0, 14))
        self.add_input_tooltip = Tooltip(self.btn_add_input, "Adicionar vídeos à linha do tempo")

        self._bind_drop_zone(self.drop_zone, icon_wrap, icon_label, self.label_file_name, self.label_input_path)

        self.options_content = ctk.CTkFrame(content, fg_color="transparent")
        self.options_content.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        self.options_content.grid_columnconfigure(0, weight=1)

        self.metadata_row = ctk.CTkFrame(self.options_content, fg_color="transparent")
        self.controls_row = ctk.CTkFrame(self.options_content, fg_color="transparent")
        self.metadata_chip_frames = []

        for column in range(4):
            self.metadata_row.grid_columnconfigure(column, weight=1, uniform="metadata")

        self.label_file_size = self._create_chip(self.metadata_row, 0, "Tamanho", "--")
        self.label_duration = self._create_chip(self.metadata_row, 1, "Duração", "--")
        self.label_resolution = self._create_chip(self.metadata_row, 2, "Resolução", "--")
        self.label_codec = self._create_chip(self.metadata_row, 3, "Codec", "--")

        self.controls_row.grid_columnconfigure(0, weight=0, minsize=150)
        self.controls_row.grid_columnconfigure(1, weight=0, minsize=112)
        self.controls_row.grid_columnconfigure(2, weight=0, minsize=58)
        self.controls_row.grid_columnconfigure(3, weight=0, minsize=48)
        self.controls_row.grid_columnconfigure(4, weight=0, minsize=84)
        self.controls_row.grid_columnconfigure(5, weight=1)

        self.combo_profile = self._create_combo(
            self.controls_row,
            list(self.compressor.COMPRESSION_PROFILES.keys()),
            width=150
        )
        self.combo_profile.configure(height=34)
        self.combo_profile.set("Balanceado")

        self.combo_resolution = self._create_combo(
            self.controls_row,
            ["Original", "1080p", "720p", "480p"],
            width=112
        )
        self.combo_resolution.configure(height=34)
        self.combo_resolution.set("Original")

        self.btn_rotate = ctk.CTkButton(
            self.controls_row,
            text="↻",
            command=self._cycle_rotation,
            font=self._font(12, "bold"),
            width=58,
            height=34,
            corner_radius=10,
            fg_color="#FFFFFF",
            hover_color="#F2F6FB",
            text_color=self.TEXT_COLOR,
            border_width=1,
            border_color=self.STRONG_BORDER_COLOR
        )

        self.btn_audio_toggle = ctk.CTkButton(
            self.controls_row,
            text="♪",
            command=self._toggle_remove_audio,
            font=self._font(13, "bold"),
            width=48,
            height=34,
            corner_radius=10,
            fg_color="#FFFFFF",
            hover_color="#F2F6FB",
            text_color=self.TEXT_COLOR,
            border_width=1,
            border_color=self.STRONG_BORDER_COLOR,
        )

        self.btn_split_clip = ctk.CTkButton(
            self.controls_row,
            text="Dividir",
            command=self._split_clip,
            font=self._font(12, "bold"),
            width=84,
            height=34,
            corner_radius=10,
            fg_color="#FFFFFF",
            hover_color="#F2F6FB",
            text_color=self.TEXT_COLOR,
            border_width=1,
            border_color=self.STRONG_BORDER_COLOR,
        )

        self.rotation_tooltip = Tooltip(self.btn_rotate, self._rotation_tooltip_text())
        self.audio_tooltip = Tooltip(self.btn_audio_toggle, self._audio_tooltip_text())
        self.split_tooltip = Tooltip(self.btn_split_clip, "Dividir clipe no tempo atual")

        self._layout_options_bar(True)

        self.label_save_rule = ctk.CTkLabel(
            content,
            text="Saída: mesma pasta do original",
            font=self._font(10),
            text_color=self.SUBTLE_TEXT_COLOR,
            anchor="w"
        )
        self.label_save_rule.grid(row=2, column=0, sticky="ew", pady=(7, 0))

    def _create_chip(self, parent, column: int, title: str, value: str) -> ctk.CTkLabel:
        chip = ctk.CTkFrame(
            parent,
            fg_color="#F5F8FC",
            corner_radius=10,
            border_width=1,
            border_color=self.BORDER_COLOR,
            height=32
        )
        chip.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 6, 0))
        chip.grid_propagate(False)
        chip.grid_columnconfigure(1, weight=1)
        if hasattr(self, "metadata_chip_frames"):
            self.metadata_chip_frames.append(chip)

        ctk.CTkLabel(
            chip,
            text=f"{title}:",
            font=self._font(9, "bold"),
            text_color=self.SUBTLE_TEXT_COLOR
        ).grid(row=0, column=0, sticky="w", padx=(8, 3), pady=6)

        value_label = ctk.CTkLabel(
            chip,
            text=value,
            font=self._font(10, "bold"),
            text_color=self.TEXT_COLOR,
            anchor="w"
        )
        value_label.grid(row=0, column=1, sticky="ew", padx=(0, 7), pady=6)
        return value_label

    def _build_editor_workspace(self, parent):
        colors = {
            "card": self.CARD_COLOR,
            "border": self.BORDER_COLOR,
            "strong_border": self.STRONG_BORDER_COLOR,
            "text": self.TEXT_COLOR,
            "muted": self.MUTED_COLOR,
            "accent": self.ACCENT_COLOR,
            "accent_hover": self.ACCENT_HOVER_COLOR,
        }
        self.editor_timeline = EditorTimeline(
            parent,
            editor_state=self.editor_state,
            font=self._font,
            colors=colors,
            on_add_blur=self._start_timeline_blur_selection,
            on_seek=self._set_current_time,
            on_filter_select=self._select_editor_filter,
            on_filter_changed=self._editor_filter_changed,
            on_filter_delete=self._delete_editor_filter,
            on_filter_duplicate=self._duplicate_editor_filter,
            on_segment_select=self._select_editor_segment,
            on_segment_delete=self._delete_editor_segment,
            on_segment_duplicate=self._duplicate_editor_segment,
            on_segment_move=self._move_editor_segment,
        )
        self.editor_timeline.grid(row=1, column=0, sticky="nsew")

    def _layout_options_bar(self, wrapped: bool):
        if not hasattr(self, "options_content") or not hasattr(self, "metadata_row"):
            return

        self.metadata_row.grid_forget()
        self.controls_row.grid_forget()
        for column in range(2):
            self.options_content.grid_columnconfigure(column, weight=0, minsize=0, uniform="")

        if wrapped:
            self.options_content.grid_rowconfigure(0, weight=0, minsize=32)
            self.options_content.grid_rowconfigure(1, weight=0, minsize=34)
            self.options_content.grid_columnconfigure(0, weight=1)
            self.metadata_row.grid(row=0, column=0, sticky="ew")
            self.controls_row.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        else:
            self.options_content.grid_rowconfigure(0, weight=0, minsize=34)
            self.options_content.grid_rowconfigure(1, weight=0, minsize=0)
            self.options_content.grid_columnconfigure(0, weight=1)
            self.options_content.grid_columnconfigure(1, weight=0)
            self.metadata_row.grid(row=0, column=0, sticky="ew", padx=(0, 10))
            self.controls_row.grid(row=0, column=1, sticky="e")

        self.combo_profile.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.combo_resolution.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        self.btn_rotate.grid(row=0, column=2, sticky="e", padx=(0, 8))
        self.btn_audio_toggle.grid(row=0, column=3, sticky="e", padx=(0, 8))
        self.btn_split_clip.grid(row=0, column=4, sticky="e")
        self._options_wrapped = wrapped

    def _cycle_rotation(self):
        if self.is_compressing:
            return

        rotation_order = (0, 90, 180, 270)
        current_index = rotation_order.index(self.rotation_degrees)
        next_rotation = rotation_order[(current_index + 1) % len(rotation_order)]
        affected_blurs = len(self.editor_state.blur_filters_for_export())

        self.editor_state.rotate_workspace(next_rotation)
        self.rotation_degrees = self.editor_state.rotation_degrees
        self._update_rotation_button()

        if hasattr(self, "video_preview"):
            self.video_preview.set_rotation(self.rotation_degrees)

        if affected_blurs:
            self._sync_editor_filters_to_preview(refresh=True)
            self._add_status(f"Rotação ajustada para {self.rotation_degrees}°. {affected_blurs} blur(s) reposicionado(s).")
        else:
            self._add_status(f"Rotação ajustada para {self.rotation_degrees}°.")

    def _rotation_shortcut(self, _event=None):
        self._cycle_rotation()
        return "break"

    def _update_rotation_button(self):
        label = "↻" if self.rotation_degrees == 0 else f"↻ {self.rotation_degrees}°"
        self.btn_rotate.configure(text=label)
        self.rotation_tooltip.set_text(self._rotation_tooltip_text())

    def _rotation_tooltip_text(self) -> str:
        next_rotation = {0: 90, 90: 180, 180: 270, 270: 0}.get(self.rotation_degrees, 90)
        return f"Girar para {next_rotation}°"

    def _reset_rotation(self):
        self.rotation_degrees = 0
        self.editor_state.set_rotation(0)
        if hasattr(self, "btn_rotate"):
            self._update_rotation_button()

        if hasattr(self, "video_preview"):
            self.video_preview.set_rotation(0)

    def _toggle_remove_audio(self):
        if self.is_compressing:
            return

        self.remove_audio = not self.remove_audio
        self._update_audio_toggle()
        self._add_status("Áudio removido." if self.remove_audio else "Áudio mantido.")

    def _audio_shortcut(self, _event=None):
        self._toggle_remove_audio()
        return "break"

    def _update_audio_toggle(self):
        if self.remove_audio:
            self.btn_audio_toggle.configure(
                text="×♪",
                fg_color=self.ACCENT_SOFT_COLOR,
                hover_color="#DDEEFF",
                text_color=self.ACCENT_COLOR,
                border_color="#B8D7FF"
            )
        else:
            self.btn_audio_toggle.configure(
                text="♪",
                fg_color="#FFFFFF",
                hover_color="#F2F6FB",
                text_color=self.TEXT_COLOR,
                border_color=self.STRONG_BORDER_COLOR
            )

        self.audio_tooltip.set_text(self._audio_tooltip_text())

    def _audio_tooltip_text(self) -> str:
        if self.remove_audio:
            return "Manter o áudio do vídeo"

        return "Remover o áudio do vídeo"

    def _split_shortcut(self, _event=None):
        self._split_clip()
        return "break"

    def _undo_shortcut(self, _event=None):
        self._undo_editor()
        return "break"

    def _redo_shortcut(self, _event=None):
        self._redo_editor()
        return "break"

    def _delete_timeline_shortcut(self, _event=None):
        self._delete_selected_timeline_item()
        return "break"

    def _update_split_button_state(self):
        if not hasattr(self, "btn_split_clip"):
            return

        can_split = (
            bool(self.input_file)
            and not self.is_compressing
            and self.editor_state.can_split_at(self.editor_state.playback.current_time)
        )
        self.btn_split_clip.configure(state="normal" if can_split else "disabled")

    def _split_clip(self):
        if self.is_compressing:
            return

        if not self.input_file:
            self._add_status("Selecione um vídeo antes de dividir.")
            self._update_split_button_state()
            return

        current_time = self.editor_state.playback.current_time
        segment, message = self.editor_state.split_segment_at(current_time)
        if segment is None:
            self._add_status(message)
            self._update_split_button_state()
            return

        self._refresh_editor_after_timeline_change(refresh_frame=False)
        self._add_status(f"Clipe dividido em {self._format_timecode(current_time)}.")

    def _delete_selected_timeline_item(self):
        if self.is_compressing:
            return

        selected_segment = self.editor_state.selected_segment()
        if selected_segment is not None:
            self._delete_editor_segment(selected_segment.id)
            return

        selected_filter = self.editor_state.selected_filter()
        if selected_filter is not None:
            self._delete_editor_filter(selected_filter.id)

    def _undo_editor(self):
        if self.editor_state.undo():
            self._refresh_editor_after_timeline_change(refresh_frame=True)
            self._add_status("Ação desfeita.")

    def _redo_editor(self):
        if self.editor_state.redo():
            self._refresh_editor_after_timeline_change(refresh_frame=True)
            self._add_status("Ação refeita.")

    def _refresh_editor_after_timeline_change(self, refresh_frame: bool = True):
        if self.rotation_degrees != self.editor_state.rotation_degrees:
            self.rotation_degrees = self.editor_state.rotation_degrees
            self._update_rotation_button()
            if hasattr(self, "video_preview"):
                self.video_preview.set_rotation(self.rotation_degrees)
        if hasattr(self, "video_preview"):
            self.video_preview.set_duration(self.editor_state.playback.duration, refresh=False)
            self.video_preview.set_time_mapper(self._map_preview_time_to_source)
        self._set_current_time(self.editor_state.playback.current_time, "timeline")
        self._sync_editor_filters_to_preview(refresh=refresh_frame)
        if hasattr(self, "editor_timeline"):
            self.editor_timeline.refresh()
        if self.input_file:
            self._update_timeline_metadata()
        self._update_split_button_state()

    def _cancel_blur_selection_shortcut(self, _event=None):
        self._pending_timeline_blur_start = None
        if hasattr(self, "video_preview"):
            self.video_preview.cancel_blur_selection()
        return "break"

    def _build_progress_card(self, parent):
        card = self._create_card(parent)
        card.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        card.grid_columnconfigure(0, weight=1)

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.grid(row=0, column=0, sticky="ew", padx=15, pady=14)
        content.grid_columnconfigure(0, weight=1)

        top_line = ctk.CTkFrame(content, fg_color="transparent")
        top_line.grid(row=0, column=0, sticky="ew")
        top_line.grid_columnconfigure(0, weight=1)

        self.label_progress_title = ctk.CTkLabel(
            top_line,
            text="Progresso",
            font=self._font(15, "bold"),
            text_color=self.TEXT_COLOR,
            anchor="w"
        )
        self.label_progress_title.grid(row=0, column=0, sticky="w")

        self.label_progress_percent = ctk.CTkLabel(
            top_line,
            text="0%",
            font=self._font(13, "bold"),
            text_color=self.ACCENT_COLOR,
            anchor="e"
        )
        self.label_progress_percent.grid(row=0, column=1, sticky="e")

        self.progress_bar = ctk.CTkProgressBar(
            content,
            height=8,
            corner_radius=7,
            fg_color="#E8EEF6",
            progress_color=self.ACCENT_COLOR
        )
        self.progress_bar.set(0)
        self.progress_bar.grid(row=1, column=0, sticky="ew", pady=(12, 8))

        self.label_progress = ctk.CTkLabel(
            content,
            text="Pronto para comprimir",
            font=self._font(11),
            text_color=self.MUTED_COLOR,
            anchor="w"
        )
        self.label_progress.grid(row=2, column=0, sticky="ew")

        self.progress_result_frame = ctk.CTkFrame(content, fg_color="transparent")
        self.progress_result_frame.grid(row=3, column=0, sticky="ew", pady=(9, 0))
        self.progress_result_frame.grid_columnconfigure(1, weight=1)

        self.progress_result_icon = ctk.CTkFrame(
            self.progress_result_frame,
            fg_color=self.SUCCESS_COLOR,
            corner_radius=12,
            width=24,
            height=24
        )
        self.progress_result_icon.grid(row=0, column=0, rowspan=3, sticky="nw", padx=(0, 9), pady=(1, 0))
        self.progress_result_icon.grid_propagate(False)
        self.progress_result_icon_label = ctk.CTkLabel(
            self.progress_result_icon,
            text="✓",
            font=self._font(14, "bold"),
            text_color="#FFFFFF"
        )
        self.progress_result_icon_label.place(relx=0.5, rely=0.47, anchor="center")

        self.label_result_sizes = ctk.CTkLabel(
            self.progress_result_frame,
            text="--",
            font=self._font(12, "bold"),
            text_color=self.TEXT_COLOR,
            anchor="w"
        )
        self.label_result_sizes.grid(row=0, column=1, sticky="ew")

        self.label_result_savings = ctk.CTkLabel(
            self.progress_result_frame,
            text="--",
            font=self._font(11),
            text_color=self.MUTED_COLOR,
            anchor="w"
        )
        self.label_result_savings.grid(row=1, column=1, sticky="ew", pady=(1, 0))

        self.label_result_time = ctk.CTkLabel(
            self.progress_result_frame,
            text="--",
            font=self._font(10),
            text_color=self.SUBTLE_TEXT_COLOR,
            anchor="w"
        )
        self.label_result_time.grid(row=2, column=1, sticky="ew", pady=(1, 0))

        result_buttons = ctk.CTkFrame(content, fg_color="transparent")
        result_buttons.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        result_buttons.grid_columnconfigure(0, weight=1, uniform="progress_result_buttons")
        result_buttons.grid_columnconfigure(1, weight=1, uniform="progress_result_buttons")
        self.progress_result_buttons = result_buttons

        self.btn_open_file = self._create_secondary_button(
            result_buttons,
            "Abrir arquivo",
            lambda: None,
            height=32
        )
        self.btn_open_file.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        self.btn_reveal_file = self._create_secondary_button(
            result_buttons,
            self._get_reveal_button_text(),
            lambda: None,
            height=32
        )
        self.btn_reveal_file.grid(row=0, column=1, sticky="ew", padx=(5, 0))

        self.progress_result_frame.grid_remove()
        self.progress_result_buttons.grid_remove()

    def _build_action_area(self, parent):
        action_frame = ctk.CTkFrame(parent, fg_color="transparent")
        action_frame.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        for column in range(2):
            action_frame.grid_columnconfigure(column, weight=1, uniform="actions")

        self.btn_compress = ctk.CTkButton(
            action_frame,
            text="Comprimir vídeo",
            command=self._start_compression,
            font=self._font(14, "bold"),
            height=44,
            corner_radius=12,
            fg_color=self.ACCENT_COLOR,
            hover_color=self.ACCENT_HOVER_COLOR,
            text_color="#FFFFFF"
        )
        self.btn_compress.grid(row=0, column=0, columnspan=2, sticky="ew")

        self.btn_extract_audio = self._create_secondary_button(
            action_frame,
            "Extrair MP3",
            self._start_audio_extraction,
            height=38
        )
        self.btn_extract_audio.grid(row=1, column=0, sticky="ew", pady=(9, 0), padx=(0, 5))

        self.btn_cancel = ctk.CTkButton(
            action_frame,
            text="Cancelar",
            command=self._cancel_compression,
            font=self._font(12, "bold"),
            height=38,
            corner_radius=10,
            fg_color="#FFFFFF",
            hover_color="#F2F6FB",
            text_color=self.DISABLED_COLOR,
            border_width=1,
            border_color=self.BORDER_COLOR,
            state="disabled"
        )
        self.btn_cancel.grid(row=1, column=1, sticky="ew", pady=(9, 0), padx=(5, 0))

    def _build_preview_card(self, parent):
        colors = {
            "card": self.CARD_COLOR,
            "border": self.BORDER_COLOR,
            "strong_border": self.STRONG_BORDER_COLOR,
            "text": self.TEXT_COLOR,
            "muted": self.MUTED_COLOR,
            "accent": self.ACCENT_COLOR,
            "accent_hover": self.ACCENT_HOVER_COLOR,
        }
        self.video_preview = VideoPreview(
            parent,
            ffmpeg_path=self.compressor.ffmpeg_path,
            font=self._font,
            colors=colors
        )
        self.video_preview.set_time_change_callback(self._on_preview_time_changed)
        self.video_preview.set_playback_change_callback(self._on_preview_playback_changed)
        self.video_preview.set_overlay_change_callback(self._on_preview_overlay_changed)
        self.video_preview.set_overlay_edit_callbacks(self._begin_preview_overlay_edit, self._end_preview_overlay_edit)
        self.video_preview.set_time_mapper(self._map_preview_time_to_source)
        self.video_preview.grid(row=2, column=0, sticky="nsew")

    def _set_current_time(self, value: float, source: str = "system"):
        if self._syncing_time:
            return

        self._syncing_time = True
        try:
            current_time = self.editor_state.playback.set_time(value, source)
            if self.editor_state.playback.is_playing:
                self._playback_tick_base_time = current_time
                self._playback_tick_started_at = time.monotonic()
            self._sync_editor_filters_to_preview(refresh=False)

            if hasattr(self, "editor_timeline"):
                if source == "player":
                    self.editor_timeline.update_playhead()
                else:
                    self.editor_timeline.refresh(redraw_inspector=False)

            if source != "player" and hasattr(self, "video_preview"):
                self.video_preview.seek_to(current_time, source=source, request_frame=True, emit=False)
        finally:
            self._syncing_time = False
            self._update_split_button_state()

    def _on_preview_time_changed(self, current_time: float, source: str):
        self._set_current_time(current_time, "player")

    def _on_preview_playback_changed(self, is_playing: bool):
        self.editor_state.playback.is_playing = is_playing
        if is_playing:
            self._start_playback_tick()
        else:
            self._cancel_playback_tick()
        if hasattr(self, "editor_timeline"):
            self.editor_timeline.update_playhead()
        self._update_split_button_state()

    def _start_playback_tick(self):
        self._cancel_playback_tick()
        self._playback_tick_base_time = self.editor_state.playback.current_time
        self._playback_tick_started_at = time.monotonic()
        self._schedule_playback_tick()

    def _schedule_playback_tick(self):
        self._playback_tick_after_id = self.root.after(40, self._run_playback_tick)

    def _cancel_playback_tick(self):
        if self._playback_tick_after_id is None:
            return
        try:
            self.root.after_cancel(self._playback_tick_after_id)
        except Exception:
            pass
        self._playback_tick_after_id = None

    def _run_playback_tick(self):
        self._playback_tick_after_id = None
        if not self.editor_state.playback.is_playing:
            return

        elapsed = time.monotonic() - self._playback_tick_started_at
        current_time = self.editor_state.playback.clamp_time(self._playback_tick_base_time + elapsed)
        self.editor_state.playback.set_time(current_time, "playback")

        active_ids = self._active_editor_filter_ids(current_time)
        if active_ids != self._last_active_filter_ids:
            self._sync_editor_filters_to_preview(refresh=False)

        if hasattr(self, "video_preview"):
            self.video_preview.seek_to(current_time, source="playback", request_frame=False, emit=False)
        if hasattr(self, "editor_timeline"):
            self.editor_timeline.update_playhead()

        self._update_split_button_state()
        if current_time >= self.editor_state.playback.duration and self.editor_state.playback.duration > 0:
            return
        self._schedule_playback_tick()

    def _active_editor_filter_ids(self, current_time: Optional[float] = None) -> set[str]:
        if current_time is None:
            current_time = self.editor_state.playback.current_time
        return {
            item.id for item in self.editor_state.filters
            if item.contains(current_time)
        }

    def _sync_editor_filters_to_preview(self, refresh: bool = True):
        if not hasattr(self, "video_preview"):
            return

        overlays = []
        selected_id = self.editor_state.playback.selected_filter_id
        current_time = self.editor_state.playback.current_time
        self._last_active_filter_ids = self._active_editor_filter_ids(current_time)
        for item in self.editor_state.filters:
            if isinstance(item, BlurFilter):
                overlays.append({
                    "id": item.id,
                    "name": item.name,
                    "region": item.region.clamped(),
                    "selected": item.id == selected_id,
                    "active": item.contains(current_time),
                })

        self.video_preview.set_editor_overlays(overlays)
        if self.editor_state.filters:
            self.video_preview.set_blur_states(
                self.editor_state.active_blur_states(current_time),
                refresh=refresh,
            )
        else:
            self.video_preview.set_editor_overlays([])
            if self.video_preview.blur_states:
                self.video_preview.set_blur_states([], refresh=refresh)

    def _reset_editor_state(self, duration: float = 0.0, source_path: str = ""):
        self.editor_state.reset(duration, source_path=source_path or (self.input_file or ""))
        self._pending_timeline_blur_start = None
        if hasattr(self, "editor_timeline"):
            self.editor_timeline.refresh()
        self._sync_editor_filters_to_preview(refresh=False)
        self._update_split_button_state()

    def _start_timeline_blur_selection(self):
        if self.is_compressing:
            return

        if not self.input_file:
            messagebox.showwarning("Blur", "Selecione um vídeo antes de adicionar blur.")
            return

        self._pending_timeline_blur_start = self.editor_state.playback.current_time
        if hasattr(self, "video_preview"):
            self.video_preview.start_blur_selection(self._set_timeline_blur_region)
        self._add_status("Desenhe a região do novo blur na prévia.")

    def _set_timeline_blur_region(self, region: NormalizedRect):
        start_time = self._pending_timeline_blur_start
        if start_time is None:
            start_time = self.editor_state.playback.current_time
        self._pending_timeline_blur_start = None

        blur = self.editor_state.add_blur(
            start_time=start_time,
            region=region,
            intensity=DEFAULT_PRIVACY_BLUR_STRENGTH,
        )
        self._set_current_time(blur.start_time, "timeline")
        self._sync_editor_filters_to_preview(refresh=True)
        self.editor_timeline.refresh()
        self._add_status(f"{blur.name} criado de {self._format_timecode(blur.start_time)} a {self._format_timecode(blur.end_time)}.")

    def _map_preview_time_to_source(self, timeline_time: float) -> Optional[tuple]:
        mapped = self.editor_state.timeline_time_to_source(timeline_time)
        if mapped is None:
            return (self.input_file, timeline_time, 0, 0) if self.input_file else None
        segment, source_time = mapped
        return (
            segment.source_path or self.input_file or "",
            source_time,
            int(segment.metadata.get("width", 0) or 0),
            int(segment.metadata.get("height", 0) or 0),
        )

    def _select_editor_filter(self, filter_id: str):
        self.editor_state.select_filter(filter_id)
        item = self.editor_state.get_filter(filter_id)
        if item is not None and not item.start_time <= self.editor_state.playback.current_time <= item.end_time:
            self._set_current_time(item.start_time, "timeline")
        self._sync_editor_filters_to_preview(refresh=True)
        self.editor_timeline.refresh()

    def _select_editor_segment(self, segment_id: str):
        segment = self.editor_state.select_segment(segment_id)
        if segment is not None and not segment.contains(self.editor_state.playback.current_time, include_end=True):
            self._set_current_time(segment.timeline_start, "timeline")
        self._sync_editor_filters_to_preview(refresh=True)
        self.editor_timeline.refresh()
        self._update_split_button_state()

    def _editor_filter_changed(self, filter_id: str):
        self._sync_editor_filters_to_preview(refresh=True)
        if hasattr(self, "editor_timeline"):
            self.editor_timeline.refresh()

    def _delete_editor_filter(self, filter_id: str):
        self.editor_state.delete_filter(filter_id)
        self._sync_editor_filters_to_preview(refresh=True)
        self.editor_timeline.refresh()
        self._add_status("Filtro removido da timeline.")

    def _delete_editor_segment(self, segment_id: str):
        success, message = self.editor_state.delete_segment_ripple(segment_id)
        if not success:
            self._add_status(message)
            return
        self._refresh_editor_after_timeline_change(refresh_frame=True)
        self._update_timeline_metadata()
        self._add_status(message)

    def _duplicate_editor_segment(self, segment_id: str):
        duplicate = self.editor_state.duplicate_segment(segment_id)
        if duplicate is None:
            self._add_status("Não foi possível duplicar o segmento.")
            return
        self._refresh_editor_after_timeline_change(refresh_frame=True)
        self._update_timeline_metadata()
        self._add_status("Segmento duplicado.")

    def _move_editor_segment(self, segment_id: str, target_index: int):
        segment = self.editor_state.move_segment_to_index(segment_id, target_index)
        if segment is None:
            self._add_status("Não foi possível mover o segmento.")
            return
        self._refresh_editor_after_timeline_change(refresh_frame=True)
        self._update_timeline_metadata()
        self._add_status("Segmento reposicionado sem criar espaços vazios.")

    def _duplicate_editor_filter(self, filter_id: str):
        duplicate = self.editor_state.duplicate_filter(filter_id)
        if duplicate is None:
            return
        self._set_current_time(duplicate.start_time, "timeline")
        self._sync_editor_filters_to_preview(refresh=True)
        self.editor_timeline.refresh()
        self._add_status(f"{duplicate.name} duplicado.")

    def _on_preview_overlay_changed(self, filter_id: str, region: NormalizedRect):
        self.editor_state.update_filter_region(filter_id, region)
        self._sync_editor_filters_to_preview(refresh=True)
        if hasattr(self, "editor_timeline"):
            self.editor_timeline.refresh()

    def _begin_preview_overlay_edit(self):
        self.editor_state.record_history()

    def _end_preview_overlay_edit(self):
        self._sync_editor_filters_to_preview(refresh=True)
        if hasattr(self, "editor_timeline"):
            self.editor_timeline.refresh()

    def _format_timecode(self, seconds: float) -> str:
        seconds = max(0.0, float(seconds or 0.0))
        minutes = int(seconds // 60)
        secs = seconds - minutes * 60
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"
        return f"{minutes:02d}:{secs:06.3f}"

    def _bind_drop_zone(self, *widgets):
        for widget in widgets:
            widget.bind("<Enter>", lambda _event: self._set_drop_hover(True))
            widget.bind("<Leave>", lambda _event: self._set_drop_hover(False))
            widget.bind("<Button-1>", self._handle_drop_zone_click)

    def _set_drop_hover(self, hovering: bool):
        if self.is_compressing:
            return

        if hovering or self.input_file:
            self.drop_zone.configure(fg_color="#F3F9FF", border_color=self.ACCENT_COLOR)
        else:
            self.drop_zone.configure(fg_color=self.SURFACE_COLOR, border_color=self.STRONG_BORDER_COLOR)

    def _handle_drop_zone_click(self, _event=None):
        if not self.is_compressing:
            self._select_input_file()

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
            self._add_status("Erro - FFmpeg não foi encontrado.")

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
            pass

    def _open_file_dialog(self, title: str, filetypes: tuple) -> Optional[str]:
        """
        Abre um diálogo de seleção de arquivo de forma robusta.

        Solução para macOS:
        - Associa o diálogo a janela principal com parent
        - Prepara a janela antes de abrir o diálogo
        - Executa na thread principal
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
            self._add_status(f"Erro ao abrir diálogo de arquivo: {str(e)}")
            return None

    def _open_files_dialog(self, title: str, filetypes: tuple) -> list[str]:
        self._prepare_window_for_dialog()

        try:
            file_paths = filedialog.askopenfilenames(
                parent=self.root,
                title=title,
                filetypes=filetypes
            )
            return [path for path in file_paths if path]
        except Exception as e:
            self._add_status(f"Erro ao abrir diálogo de arquivos: {str(e)}")
            return []

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

        self._load_timeline_from_files([file_path])

    def _add_input_files_dialog(self):
        """Adiciona um ou mais vídeos à timeline existente."""
        if self.is_compressing:
            return

        video_formats = (
            ("Arquivos de Vídeo (*.mp4 *.mov *.mkv *.avi *.wmv *.flv *.webm *.m4v *.mpeg *.mpg *.3gp *.ts *.mts *.m2ts)",
             "*.mp4 *.mov *.mkv *.avi *.wmv *.flv *.webm *.m4v *.mpeg *.mpg *.3gp *.ts *.mts *.m2ts"),
            ("Todos os arquivos", "*.*")
        )

        file_paths = self._open_files_dialog(
            title="Adicione vídeos à linha do tempo",
            filetypes=video_formats
        )
        if not file_paths:
            return

        if not self.input_file:
            self._load_timeline_from_files(file_paths)
            return

        selected = self.editor_state.selected_segment()
        if selected is not None:
            insert_index = self.editor_state.segments.index(selected) + 1
        else:
            insert_index = self.editor_state.insertion_index_for_time(self.editor_state.playback.current_time)

        added = []
        for file_path in file_paths:
            segment = self._add_video_segment(file_path, insert_index=insert_index)
            if segment is not None:
                added.append(segment)
                insert_index += 1

        if not added:
            messagebox.showerror("Erro", "Não foi possível adicionar os vídeos selecionados.")
            return

        self._refresh_loaded_timeline(seek_time=added[0].timeline_start)
        self._add_status(f"{len(added)} vídeo(s) adicionado(s) à linha do tempo.")

    def _load_timeline_from_files(self, file_paths: list[str]):
        if not file_paths:
            return

        self.input_file = file_paths[0]
        self._reset_rotation()
        self.editor_state.reset(0.0)
        self.editor_state.set_rotation(self.rotation_degrees)

        added = []
        for file_path in file_paths:
            segment = self._add_video_segment(file_path, insert_index=len(self.editor_state.segments))
            if segment is not None:
                added.append(segment)

        if not added:
            self.input_file = None
            messagebox.showerror(
                "Erro",
                "Não foi possível ler as informações do vídeo.\n"
                "Verifique se o arquivo é válido."
            )
            self.label_file_name.configure(text="Selecione ou arraste um vídeo")
            self.label_input_path.configure(text="Erro ao ler arquivo")
            self.btn_select_input.configure(text="Selecionar vídeo")
            self._set_metadata_placeholders()
            self.drop_zone.configure(fg_color=self.SURFACE_COLOR, border_color=self.STRONG_BORDER_COLOR)
            self.video_preview.show_unavailable("Prévia indisponível para este vídeo.")
            self._reset_editor_state(0.0)
            return

        self.editor_state.clear_history()
        self._refresh_loaded_timeline(seek_time=0.0)
        self._add_status(f"{len(added)} vídeo(s) carregado(s) na linha do tempo.")

    def _add_video_segment(self, file_path: str, insert_index: Optional[int] = None):
        info = self.compressor.get_video_info(file_path)
        if not info:
            self._add_status(f"Não foi possível ler: {Path(file_path).name}.")
            return None

        codec = self._get_video_codec(file_path)
        metadata = {
            "name": Path(file_path).name,
            "file_size": info.get("file_size", 0),
            "width": info.get("width", 0),
            "height": info.get("height", 0),
            "codec": codec,
        }
        return self.editor_state.add_media_segment(
            file_path,
            float(info.get("duration", 0) or 0),
            insert_index=insert_index,
            metadata=metadata,
        )

    def _refresh_loaded_timeline(self, seek_time: float = 0.0):
        if not self.input_file or not self.editor_state.segments:
            return

        self._update_timeline_metadata()
        first = self.editor_state.segments[0]
        first_size = (
            int(first.metadata.get("width", 0) or 0),
            int(first.metadata.get("height", 0) or 0),
        )
        self.video_preview.load(
            first.source_path or self.input_file,
            self.editor_state.playback.duration,
            rotation_degrees=self.rotation_degrees,
            source_size=first_size,
        )
        self.video_preview.set_time_mapper(self._map_preview_time_to_source)
        self._set_current_time(seek_time, "system")
        self._sync_editor_filters_to_preview(refresh=True)
        if hasattr(self, "editor_timeline"):
            self.editor_timeline.refresh()
        self._update_split_button_state()

    def _update_timeline_metadata(self):
        segments = self.editor_state.segments_for_export()
        if not segments:
            self._set_metadata_placeholders()
            return

        total_size = sum(int(segment.metadata.get("file_size", 0) or 0) for segment in segments)
        total_mb = total_size / (1024 * 1024)
        total_duration = self.editor_state.playback.duration
        widths = {int(segment.metadata.get("width", 0) or 0) for segment in segments}
        heights = {int(segment.metadata.get("height", 0) or 0) for segment in segments}
        codecs = {segment.metadata.get("codec", "--") for segment in segments}

        if len(segments) == 1:
            segment = segments[0]
            file_name = Path(segment.source_path).name
            parent_folder = str(Path(segment.source_path).parent)
            self.label_file_name.configure(text=self._shorten_text(file_name, 46))
            self.label_input_path.configure(text=self._shorten_path(parent_folder, 62))
            self.label_resolution.configure(text=f"{segment.metadata.get('width', 0)}x{segment.metadata.get('height', 0)}")
            self.label_codec.configure(text=segment.metadata.get("codec", "--"))
        else:
            self.label_file_name.configure(text=f"{len(segments)} vídeos na linha do tempo")
            self.label_input_path.configure(text=f"Primeiro: {self._shorten_text(Path(segments[0].source_path).name, 48)}")
            if len(widths) == 1 and len(heights) == 1:
                self.label_resolution.configure(text=f"{widths.pop()}x{heights.pop()}")
            else:
                self.label_resolution.configure(text="Vários")
            self.label_codec.configure(text=codecs.pop() if len(codecs) == 1 else "Vários")

        self.btn_select_input.configure(text="Trocar vídeo")
        self.drop_zone.configure(fg_color="#F3F9FF", border_color=self.ACCENT_COLOR)
        self.label_file_size.configure(text=f"{self._format_decimal(total_mb, 2)} MB")
        self.label_duration.configure(text=str(timedelta(seconds=int(total_duration))))

    def _update_input_info(self):
        """Atualiza as informações do arquivo selecionado."""
        if not self.input_file:
            return

        file_name = Path(self.input_file).name
        parent_folder = str(Path(self.input_file).parent)
        self.label_file_name.configure(text=self._shorten_text(file_name, 46))
        self.label_input_path.configure(text=self._shorten_path(parent_folder, 62))
        self.btn_select_input.configure(text="Trocar vídeo")
        self.drop_zone.configure(fg_color="#F3F9FF", border_color=self.ACCENT_COLOR)

        info = self.compressor.get_video_info(self.input_file)

        if info:
            duration = float(info.get("duration", 0) or 0)
            self._reset_editor_state(duration, self.input_file)
            size_mb = info['file_size'] / (1024 * 1024)
            self.label_file_size.configure(text=f"{self._format_decimal(size_mb, 2)} MB")

            duration_str = str(timedelta(seconds=int(duration)))
            self.label_duration.configure(text=duration_str)

            resolution_str = f"{info['width']}x{info['height']}"
            self.label_resolution.configure(text=resolution_str)

            codec = self._get_video_codec(self.input_file)
            self.label_codec.configure(text=codec)
            self.video_preview.load(
                self.input_file,
                duration,
                rotation_degrees=self.rotation_degrees,
                source_size=(info.get("width", 0), info.get("height", 0)),
            )
            self.video_preview.set_time_mapper(self._map_preview_time_to_source)
            self._set_current_time(0.0, "system")

            self._add_status(f"Arquivo carregado: {file_name} ({size_mb:.2f} MB).")
        else:
            messagebox.showerror(
                "Erro",
                "Não foi possível ler as informações do vídeo.\n"
                "Verifique se o arquivo é válido."
            )
            self.input_file = None
            self.label_file_name.configure(text="Selecione ou arraste um vídeo")
            self.label_input_path.configure(text="Erro ao ler arquivo")
            self.btn_select_input.configure(text="Selecionar vídeo")
            self._set_metadata_placeholders()
            self.drop_zone.configure(fg_color=self.SURFACE_COLOR, border_color=self.STRONG_BORDER_COLOR)
            self.video_preview.show_unavailable("Prévia indisponível para este vídeo.")
            self._reset_editor_state(0.0)
            self._reset_rotation()

    def _get_video_codec(self, file_path: str) -> str:
        """Obtém o codec apenas para apresentação visual na interface."""
        try:
            cmd = [
                self.compressor.ffprobe_path,
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=codec_name",
                "-of", "json",
                file_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode != 0:
                return "--"

            data = json.loads(result.stdout)
            streams = data.get("streams", [])
            if not streams:
                return "--"

            codec = streams[0].get("codec_name", "--")
            return self._humanize_codec(codec)
        except Exception:
            return "--"

    def _humanize_codec(self, codec: str) -> str:
        codec_map = {
            "h264": "H.264",
            "hevc": "HEVC",
            "h265": "H.265",
            "mpeg4": "MPEG-4",
            "prores": "ProRes",
            "vp9": "VP9",
            "av1": "AV1"
        }
        return codec_map.get(codec.lower(), codec.upper())

    def _build_unique_output_path(self, suffix: str, extension: str) -> str:
        """Gera um caminho seguro ao lado do vídeo original sem sobrescrever."""
        input_path = Path(self.input_file)
        folder = input_path.parent
        base_name = f"{input_path.stem}{suffix}"
        extension = extension if extension.startswith(".") else f".{extension}"

        candidate = folder / f"{base_name}{extension}"
        counter = 2

        while candidate.exists() or candidate.resolve() == input_path.resolve():
            candidate = folder / f"{base_name}_{counter}{extension}"
            counter += 1

        return str(candidate)

    def _start_compression(self):
        """Inicia o processo de compressão."""
        if not self.input_file:
            messagebox.showwarning("Erro", "Por favor, selecione um arquivo de vídeo.")
            return

        if not self.compressor.is_ffmpeg_available():
            messagebox.showerror(
                "Erro",
                "FFmpeg não está acessível. Verifique a instalação."
            )
            return

        original_folder = str(Path(self.input_file).parent)

        if not os.path.isdir(original_folder):
            messagebox.showerror("Erro", "A pasta do vídeo original não está acessível.")
            return

        temporal_blurs = self.editor_state.blur_filters_for_export()
        segments = self.editor_state.segments_for_export()

        output_file = self._build_unique_output_path("_comprimido", ".mp4")

        self.processing_temporal_blurs = list(temporal_blurs)
        self.processing_segments = list(segments)
        self.processing_blur_enabled = bool(temporal_blurs)
        self._prepare_processing_state("Preparando compressão")
        self.is_compressing = True
        self._set_processing_controls(True)

        self.compression_thread = threading.Thread(
            target=self._compression_worker,
            args=(output_file,),
            daemon=True
        )
        self.compression_thread.start()

    def _start_audio_extraction(self):
        """Inicia a extração do áudio em MP3."""
        if not self.input_file:
            messagebox.showwarning("Erro", "Por favor, selecione um arquivo de vídeo.")
            return

        if not self.compressor.is_ffmpeg_available():
            messagebox.showerror(
                "Erro",
                "FFmpeg não está acessível. Verifique a instalação."
            )
            return

        original_folder = str(Path(self.input_file).parent)

        if not os.path.isdir(original_folder):
            messagebox.showerror("Erro", "A pasta do vídeo original não está acessível.")
            return

        output_file = self._build_unique_output_path("", ".mp3")

        self.processing_temporal_blurs = []
        self.processing_segments = []
        self.processing_blur_enabled = False
        self._prepare_processing_state("Preparando extração de áudio")
        self.is_compressing = True
        self._set_processing_controls(True)

        self.compression_thread = threading.Thread(
            target=self._audio_extraction_worker,
            args=(output_file,),
            daemon=True
        )
        self.compression_thread.start()

    def _prepare_processing_state(self, message: str):
        self.processing_started_at = time.monotonic()
        self.last_operation_succeeded = False
        self.last_output_file = None
        self.processing_terminal_message = None
        if self.video_preview.pause_for_processing():
            self._add_status("Prévia pausada durante o processamento.")
        self._reset_progress_result()
        self.progress_bar.set(0)
        self.label_progress_title.configure(text="Comprimindo vídeo", text_color=self.TEXT_COLOR)
        self.label_progress.configure(text=message)
        self.label_progress_percent.configure(text="0%")

    def _set_processing_controls(self, running: bool):
        if running:
            self.btn_compress.configure(state="disabled")
            self.btn_extract_audio.configure(state="disabled")
            self.btn_cancel.configure(
                state="normal",
                fg_color="#FFFFFF",
                hover_color=self.DANGER_SOFT_COLOR,
                text_color=self.DANGER_COLOR,
                border_color="#FFD2CE"
            )
            self.btn_select_input.configure(state="disabled")
            self.btn_add_input.configure(state="disabled")
            self.combo_profile.configure(state="disabled")
            self.combo_resolution.configure(state="disabled")
            self.btn_rotate.configure(state="disabled")
            self.btn_audio_toggle.configure(state="disabled")
            self.btn_split_clip.configure(state="disabled")
            if hasattr(self, "editor_timeline"):
                self.editor_timeline.set_enabled(False)
            return

        self.btn_compress.configure(state="normal")
        self.btn_extract_audio.configure(state="normal")
        self.btn_cancel.configure(
            state="disabled",
            fg_color="#FFFFFF",
            hover_color="#F2F6FB",
            text_color=self.DISABLED_COLOR,
            border_color=self.BORDER_COLOR
        )
        self.btn_select_input.configure(state="normal")
        self.btn_add_input.configure(state="normal")
        self.combo_profile.configure(state="readonly")
        self.combo_resolution.configure(state="readonly")
        self.btn_rotate.configure(state="normal")
        self.btn_audio_toggle.configure(state="normal")
        self._update_split_button_state()
        if hasattr(self, "editor_timeline"):
            self.editor_timeline.set_enabled(True)

    def _reset_progress_result(self):
        self.label_progress_title.configure(text="Progresso", text_color=self.TEXT_COLOR)
        self.label_progress_percent.grid()
        self.progress_bar.grid()
        self.progress_result_frame.grid_remove()
        self.progress_result_buttons.grid_remove()
        self.progress_result_icon.configure(fg_color=self.SUCCESS_COLOR)
        self.progress_result_icon_label.configure(text="✓")
        self.label_result_sizes.configure(text="--")
        self.label_result_savings.configure(text="--")
        self.label_result_time.configure(text="--")
        self.btn_open_file.configure(state="disabled", command=lambda: None)
        self.btn_reveal_file.configure(
            text=self._get_reveal_button_text(),
            state="disabled",
            command=lambda: None
        )

    def _compression_worker(self, output_file: str):
        """Thread worker para compressão."""
        try:
            profile = self.combo_profile.get()
            resolution_text = self.combo_resolution.get()
            rotation = self.rotation_degrees
            remove_audio = self.remove_audio
            temporal_blurs = list(self.processing_temporal_blurs)
            segments = list(self.processing_segments)

            resolution_map = {
                "Original": 0,
                "1080p": 1080,
                "720p": 720,
                "480p": 480
            }
            resolution = resolution_map.get(resolution_text, 0)

            audio_status = "removido" if remove_audio else "mantido"
            blur_status = "com blur temporal" if temporal_blurs else "sem blur"
            edit_status = "com cortes" if len(segments) > 1 else "sem cortes"
            self._add_status(
                f"Iniciando compressão com perfil '{profile}', resolução '{resolution_text}', "
                f"rotação {rotation}°, áudio {audio_status}, {blur_status} e {edit_status}."
            )

            success, message = self.compressor.compress_video(
                self.input_file,
                output_file,
                profile=profile,
                resolution=resolution,
                remove_audio=remove_audio,
                rotation=rotation,
                temporal_blurs=temporal_blurs,
                segments=segments,
                progress_callback=self._update_progress
            )

            if success:
                self._show_results(output_file)
            else:
                self.processing_terminal_message = "Não foi possível concluir a compressão."
                self._add_status(f"Erro: {message}")
                self.root.after(0, lambda msg=message: messagebox.showerror("Erro na Compressão", msg))

        except Exception as e:
            error_message = str(e)
            self.processing_terminal_message = "Erro inesperado durante a compressão."
            self._add_status(f"Exceção: {error_message}")
            self.root.after(0, lambda msg=error_message: messagebox.showerror("Erro", f"Erro inesperado: {msg}"))

        finally:
            self.is_compressing = False
            self.root.after(0, self._compression_finished)

    def _audio_extraction_worker(self, output_file: str):
        """Thread worker para extração de áudio."""
        try:
            self._add_status("Iniciando extração de áudio em MP3.")

            success, message = self.compressor.extract_audio_mp3(
                self.input_file,
                output_file,
                progress_callback=self._update_progress
            )

            if success:
                self._show_audio_results(output_file)
            else:
                self.processing_terminal_message = "Não foi possível extrair o áudio."
                self._add_status(f"Erro: {message}")
                self.root.after(0, lambda msg=message: messagebox.showerror("Erro na Extração", msg))

        except Exception as e:
            error_message = str(e)
            self.processing_terminal_message = "Erro inesperado durante a extração."
            self._add_status(f"Exceção: {error_message}")
            self.root.after(0, lambda msg=error_message: messagebox.showerror("Erro", f"Erro inesperado: {msg}"))

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
        progress = max(0, min(100, progress))
        self.progress_bar.set(progress / 100)
        self.label_progress_percent.configure(text=f"{progress}%")
        self.label_progress.configure(text=self._progress_message(progress))

    def _progress_message(self, progress: int) -> str:
        elapsed = ""
        if self.processing_started_at is not None and self.is_compressing:
            elapsed = f" · {self._elapsed_processing_time()}"

        if progress <= 0:
            return f"Preparando vídeo{elapsed}"
        if progress < 25:
            return f"Processando frames{elapsed}"
        if progress < 55:
            step = "Aplicando blur" if self.processing_blur_enabled else "Otimizando vídeo"
            return f"{step}{elapsed}"
        if progress < 85:
            return f"Refinando saída{elapsed}"
        if progress < 100:
            return f"Finalizando arquivo{elapsed}"
        return "Processamento concluído"

    def _show_results(self, output_file: str):
        """Mostra os resultados da compressão."""
        try:
            input_size = os.path.getsize(self.input_file)
            output_size = os.path.getsize(output_file)
            reduction_percent = ((input_size - output_size) / input_size) * 100
            saved_mb = (input_size - output_size) / (1024 * 1024)

            input_mb = input_size / (1024 * 1024)
            output_mb = output_size / (1024 * 1024)
            elapsed = self._elapsed_processing_time()

            self.last_operation_succeeded = True
            self.last_output_file = output_file

            self._add_status("Compressão concluída com sucesso.")
            self._add_status(f"Tamanho original: {input_mb:.2f} MB.")
            self._add_status(f"Tamanho final: {output_mb:.2f} MB.")
            self._add_status(f"Redução: {reduction_percent:.1f}%.")
            self._add_status(f"Arquivo salvo em: {output_file}.")

            self.root.after(
                0,
                lambda: self._render_progress_result(
                    title="Compressão concluída",
                    subtitle=f"{self._format_decimal(saved_mb, 2)} MB",
                    input_file=self.input_file,
                    output_file=output_file,
                    original_size=f"{self._format_decimal(input_mb, 2)} MB",
                    final_size=f"{self._format_decimal(output_mb, 2)} MB",
                    savings=f"{self._format_decimal(reduction_percent, 1)}%",
                    elapsed=elapsed
                )
            )

        except Exception as e:
            self._add_status(f"Erro ao obter informações: {str(e)}")

    def _show_audio_results(self, output_file: str):
        """Mostra os resultados da extração de áudio."""
        try:
            input_size = os.path.getsize(self.input_file)
            output_size = os.path.getsize(output_file)
            reduction_percent = ((input_size - output_size) / input_size) * 100 if input_size > 0 else 0
            input_mb = input_size / (1024 * 1024)
            output_mb = output_size / (1024 * 1024)
            elapsed = self._elapsed_processing_time()

            self.last_operation_succeeded = True
            self.last_output_file = output_file

            self._add_status("Áudio extraído com sucesso.")
            self._add_status(f"Tamanho do MP3: {output_mb:.2f} MB.")
            self._add_status(f"Arquivo salvo em: {output_file}.")

            self.root.after(
                0,
                lambda: self._render_progress_result(
                    title="Áudio extraído",
                    subtitle="MP3 gerado com sucesso",
                    input_file=self.input_file,
                    output_file=output_file,
                    original_size=f"{self._format_decimal(input_mb, 2)} MB",
                    final_size=f"{self._format_decimal(output_mb, 2)} MB",
                    savings=f"{self._format_decimal(reduction_percent, 1)}%",
                    elapsed=elapsed
                )
            )

        except Exception as e:
            self._add_status(f"Erro ao obter informações do MP3: {str(e)}")

    def _render_progress_result(
        self,
        title: str,
        subtitle: str,
        input_file: str,
        output_file: str,
        original_size: str,
        final_size: str,
        savings: str,
        elapsed: str
    ):
        self.label_progress_title.configure(text=title, text_color=self.TEXT_COLOR)
        self.label_progress_percent.grid_remove()
        self.progress_bar.grid_remove()
        self.label_progress.configure(text="Arquivo salvo na mesma pasta do original")
        self.progress_result_icon.configure(fg_color=self.SUCCESS_COLOR)
        self.progress_result_icon_label.configure(text="✓")
        self.label_result_sizes.configure(text=f"{original_size} → {final_size}")

        if title == "Compressão concluída":
            self.label_result_savings.configure(text=f"Economia de {savings} · {subtitle}")
        else:
            self.label_result_savings.configure(text=f"Arquivo gerado · {final_size}")

        self.label_result_time.configure(
            text=f"Tempo: {elapsed} · {self._shorten_text(Path(output_file).name, 34)}"
        )
        self.btn_open_file.configure(
            state="normal",
            command=lambda path=output_file: self._open_file(path)
        )
        self.btn_reveal_file.configure(
            text=self._get_reveal_button_text(),
            state="normal",
            command=lambda path=output_file: self._reveal_file(path)
        )
        self.progress_result_frame.grid()
        self.progress_result_buttons.grid()

    def _elapsed_processing_time(self) -> str:
        if self.processing_started_at is None:
            return "--"

        elapsed = max(0.0, time.monotonic() - self.processing_started_at)
        elapsed_seconds = int(round(elapsed))

        minutes, seconds = divmod(elapsed_seconds, 60)
        if minutes < 60:
            return f"{minutes:02d}:{seconds:02d}"

        hours, minutes = divmod(minutes, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _format_decimal(self, value: float, digits: int) -> str:
        return f"{value:.{digits}f}".replace(".", ",")

    def _get_reveal_button_text(self) -> str:
        system = platform.system()
        if system == "Darwin":
            return "Mostrar no Finder"
        if system == "Windows":
            return "Mostrar no Explorer"
        return "Mostrar na pasta"

    def _open_file(self, file_path: str):
        """Abre o arquivo gerado no aplicativo padrão do sistema."""
        try:
            system = platform.system()
            if system == "Darwin":
                subprocess.Popen(["open", file_path])
            elif system == "Windows":
                os.startfile(file_path)
            else:
                subprocess.Popen(["xdg-open", file_path])
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível abrir o arquivo: {str(e)}")

    def _reveal_file(self, file_path: str):
        """Mostra o arquivo gerado no Finder, Explorer ou gerenciador de arquivos."""
        try:
            system = platform.system()
            if system == "Darwin":
                subprocess.Popen(["open", "-R", file_path])
            elif system == "Windows":
                subprocess.Popen(["explorer", f"/select,{os.path.normpath(file_path)}"])
            else:
                self._open_output_folder(file_path)
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível mostrar o arquivo: {str(e)}")

    def _open_output_folder(self, file_path: str):
        """Abre a pasta contendo o arquivo."""
        try:
            folder = os.path.dirname(file_path)
            system = platform.system()
            if system == "Darwin":
                subprocess.Popen(["open", folder])
            elif system == "Windows":
                os.startfile(folder)
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível abrir a pasta: {str(e)}")

    def _cancel_compression(self):
        """Cancela a compressão em andamento."""
        if messagebox.askyesno("Cancelar", "Deseja realmente cancelar o processamento?"):
            self.compressor.cancel_compression()
            self.last_operation_succeeded = False
            self.processing_terminal_message = "Processamento cancelado."
            self._add_status("Processamento cancelado pelo usuário.")
            self._compression_finished()

    def _compression_finished(self):
        """Chamado quando a compressão termina (com sucesso ou erro)."""
        self._set_processing_controls(False)

        if self.last_operation_succeeded:
            if not self.progress_result_frame.winfo_ismapped():
                self.progress_bar.set(1)
                self.label_progress_percent.configure(text="100%")
                self.label_progress.configure(text="Processamento concluído")
        else:
            self.progress_bar.set(0)
            self.label_progress_percent.configure(text="0%")
            self.label_progress_title.configure(text="Erro", text_color=self.DANGER_COLOR)
            self.label_progress.configure(text=self.processing_terminal_message or "Aguardando arquivo")

    def _shorten_text(self, text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text

        if max_chars <= 3:
            return text[:max_chars]

        keep = max_chars - 1
        head = keep // 2
        tail = keep - head
        return f"{text[:head]}…{text[-tail:]}"

    def _shorten_path(self, path: str, max_chars: int) -> str:
        normalized = os.path.normpath(path)
        if len(normalized) <= max_chars:
            return normalized

        path_obj = Path(normalized)
        tail = str(path_obj.name)
        parent = path_obj.parent.name
        compact = os.path.join("…", parent, tail) if parent else os.path.join("…", tail)

        if len(compact) <= max_chars:
            return compact

        return self._shorten_text(normalized, max_chars)

    def _add_status(self, message: str):
        """Registra uma mensagem interna sem ocupar espaço na interface."""
        if threading.current_thread() is not self.ui_thread:
            self.root.after(0, lambda msg=message: self._append_status(msg))
            return

        self._append_status(message)

    def _append_status(self, message: str):
        if message == self.last_status_message:
            return

        self.last_status_message = message
        self.status_messages.append(message)
