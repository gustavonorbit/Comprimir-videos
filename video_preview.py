"""
Pré-visualização leve de vídeo embutida na UI.

Este componente usa FFmpeg para extrair frames PNG em memória e renderiza com
tk.PhotoImage. Não reproduz áudio e não depende de player externo instalado.
"""

import os
import subprocess
import threading
import time
from typing import Callable, Optional

import customtkinter as ctk
import tkinter as tk

from blur_state import BlurState, NormalizedRect
from video_filters import build_video_filter, rotated_dimensions


class PreviewMuteButton:
    """Botão leve com ícone desenhado localmente, sem dependência externa."""

    def __init__(self, parent, command: Callable, colors: dict, size: int = 36):
        self.parent = parent
        self.command = command
        self.colors = colors
        self.size = size
        self.is_muted = True
        self.is_hovered = False
        self.tip_window = None
        self.tooltip_after_id = None

        self.frame = ctk.CTkFrame(
            parent,
            width=size,
            height=size,
            corner_radius=10,
            fg_color="#FFFFFF",
            border_width=1,
            border_color=colors["strong_border"]
        )
        self.frame.grid_propagate(False)

        self.canvas = tk.Canvas(
            self.frame,
            width=size - 12,
            height=size - 12,
            highlightthickness=0,
            bd=0,
            bg="#FFFFFF"
        )
        self.canvas.place(relx=0.5, rely=0.5, anchor="center")

        for widget in (self.frame, self.canvas):
            widget.bind("<Button-1>", self._handle_click)
            widget.bind("<Enter>", self._handle_enter)
            widget.bind("<Leave>", self._handle_leave)

        self._render()

    def grid(self, **kwargs):
        self.frame.grid(**kwargs)

    def grid_remove(self):
        self.frame.grid_remove()

    def set_muted(self, muted: bool):
        self.is_muted = muted
        self._render()

    def _handle_click(self, _event=None):
        self._hide_tooltip()
        self.command()

    def _handle_enter(self, _event=None):
        self.is_hovered = True
        self._render()
        self._schedule_tooltip()

    def _handle_leave(self, _event=None):
        self.is_hovered = False
        self._render()
        self._hide_tooltip()

    def _schedule_tooltip(self):
        self._cancel_tooltip()
        self.tooltip_after_id = self.frame.after(450, self._show_tooltip)

    def _show_tooltip(self):
        self.tooltip_after_id = None
        if self.tip_window:
            return

        x = max(0, self.frame.winfo_rootx() - 88)
        y = self.frame.winfo_rooty() + self.size + 8
        self.tip_window = tk.Toplevel(self.frame)
        self.tip_window.wm_overrideredirect(True)
        self.tip_window.wm_geometry(f"+{x}+{y}")

        label = tk.Label(
            self.tip_window,
            text=self._tooltip_text(),
            background="#111827",
            foreground="#FFFFFF",
            borderwidth=0,
            padx=8,
            pady=5,
            font=("Arial", 11)
        )
        label.pack()

    def _hide_tooltip(self, _event=None):
        self._cancel_tooltip()
        if self.tip_window:
            try:
                self.tip_window.destroy()
            except Exception:
                pass
            self.tip_window = None

    def _cancel_tooltip(self):
        if self.tooltip_after_id is not None:
            try:
                self.frame.after_cancel(self.tooltip_after_id)
            except Exception:
                pass
            self.tooltip_after_id = None

    def _tooltip_text(self) -> str:
        if self.is_muted:
            return "Ativar áudio da prévia"
        return "Silenciar prévia"

    def _render(self):
        if self.is_muted:
            bg_color = "#F8FAFC" if self.is_hovered else "#FFFFFF"
            border_color = self.colors["strong_border"]
            icon_color = self.colors["muted"]
        else:
            bg_color = "#DDEEFF" if self.is_hovered else "#EAF4FF"
            border_color = "#B8D7FF"
            icon_color = self.colors["accent"]

        self.frame.configure(fg_color=bg_color, border_color=border_color)
        self.canvas.configure(bg=bg_color)
        self._draw_icon(icon_color)

    def _draw_icon(self, icon_color: str):
        self.canvas.delete("all")

        self.canvas.create_polygon(
            4, 10,
            8, 10,
            14, 6,
            14, 18,
            8, 14,
            4, 14,
            fill=icon_color,
            outline=icon_color
        )

        if self.is_muted:
            self.canvas.create_line(17, 8, 22, 16, fill=icon_color, width=2, capstyle=tk.ROUND)
            self.canvas.create_line(22, 8, 17, 16, fill=icon_color, width=2, capstyle=tk.ROUND)
            return

        self.canvas.create_arc(
            13, 8, 21, 16,
            start=-45,
            extent=90,
            style=tk.ARC,
            outline=icon_color,
            width=2
        )
        self.canvas.create_arc(
            11, 5, 25, 19,
            start=-45,
            extent=90,
            style=tk.ARC,
            outline=icon_color,
            width=2
        )


class VideoPreview:
    """Preview básico por frames para CustomTkinter."""

    FRAME_INTERVAL_MS = 160
    TIME_LABEL_INTERVAL_MS = 140
    HANDLE_VISIBLE_SIZE = 8
    HANDLE_HOVER_SIZE = 10
    HANDLE_ACTIVE_SIZE = 11
    HANDLE_SIDE_HIT_RADIUS = 10
    HANDLE_CORNER_HIT_RADIUS = 12
    HANDLE_EDGE_HIT_RADIUS = 7

    def __init__(
        self,
        parent,
        ffmpeg_path: str,
        font: Callable,
        colors: dict
    ):
        self.ffmpeg_path = ffmpeg_path
        self.font = font
        self.colors = colors
        self.media_path: Optional[str] = None
        self.duration = 0.0
        self.current_time = 0.0
        self.source_width = 0
        self.source_height = 0
        self.rotation_degrees = 0
        self.blur_states: list[BlurState] = []
        self.editor_overlays: list[dict] = []
        self.is_playing = False
        self.is_muted = True
        self.is_destroyed = False
        self.editing_enabled = True
        self.is_selecting_blur_region = False
        self._time_change_callback: Optional[Callable[[float, str], None]] = None
        self._playback_change_callback: Optional[Callable[[bool], None]] = None
        self._overlay_change_callback: Optional[Callable[[str, NormalizedRect], None]] = None
        self._overlay_edit_start_callback: Optional[Callable[[], None]] = None
        self._overlay_edit_end_callback: Optional[Callable[[], None]] = None
        self._time_mapper: Optional[Callable[[float], Optional[tuple]]] = None
        self._blur_region_callback: Optional[Callable[[NormalizedRect], None]] = None
        self._selection_start: Optional[tuple[float, float]] = None
        self._selection_current: Optional[tuple[float, float]] = None
        self._overlay_drag: Optional[dict] = None
        self._overlay_hover_mode: Optional[str] = None
        self._overlay_active_mode: Optional[str] = None
        self._request_id = 0
        self._frame_in_flight = False
        self._in_flight_request_id: Optional[int] = None
        self._pending_frame_seconds: Optional[float] = None
        self._play_after_id = None
        self._seek_after_id = None
        self._stage_resize_after_id = None
        self._current_image = None
        self._playback_started_at = 0.0
        self._playback_base_time = 0.0
        self._last_time_label_update_at = 0.0
        self._metrics_window_started_at = time.perf_counter()
        self._frame_metrics = {
            "started": 0,
            "applied": 0,
            "dropped": 0,
            "errors": 0,
            "queued": 0,
            "total_ms": 0.0,
            "max_ms": 0.0,
        }

        self.frame = ctk.CTkFrame(
            parent,
            fg_color=colors["card"],
            corner_radius=14,
            border_width=1,
            border_color=colors["border"]
        )
        self.frame.grid_columnconfigure(0, weight=1)
        self.frame.grid_rowconfigure(1, weight=1)

        self._build_ui()
        self.show_empty()

    def _build_ui(self):
        header = ctk.CTkFrame(self.frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=(15, 16), pady=(13, 9))
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0, minsize=38)

        ctk.CTkLabel(
            header,
            text="Prévia",
            font=self.font(15, "bold"),
            text_color=self.colors["text"],
            anchor="w"
        ).grid(row=0, column=0, sticky="w")

        self.btn_mute = PreviewMuteButton(header, self.toggle_mute, self.colors)
        self.btn_mute.grid(row=0, column=1, sticky="e")

        self.stage = ctk.CTkFrame(
            self.frame,
            fg_color="#111827",
            corner_radius=12,
            border_width=0
        )
        self.stage.grid(row=1, column=0, sticky="nsew", padx=15)
        self.stage.grid_columnconfigure(0, weight=1)
        self.stage.grid_rowconfigure(0, weight=1)

        self.image_label = tk.Canvas(
            self.stage,
            bg="#111827",
            highlightthickness=0,
            bd=0
        )
        self.image_label.grid(row=0, column=0, sticky="nsew")
        self.stage.bind("<Configure>", self._on_stage_resize)
        self.image_label.bind("<ButtonPress-1>", self._on_blur_selection_press)
        self.image_label.bind("<B1-Motion>", self._on_blur_selection_drag)
        self.image_label.bind("<ButtonRelease-1>", self._on_blur_selection_release)
        self.image_label.bind("<Motion>", self._on_overlay_motion)
        self.image_label.bind("<Leave>", self._on_overlay_leave)

        self.empty_state = ctk.CTkFrame(
            self.stage,
            fg_color="#111827",
            corner_radius=0
        )
        self.empty_state.grid_columnconfigure(0, weight=1)

        self.empty_icon_label = ctk.CTkLabel(
            self.empty_state,
            text="▷",
            font=self.font(23, "bold"),
            text_color="#D1D5DB",
            anchor="center"
        )
        self.empty_icon_label.grid(row=0, column=0, sticky="ew")

        self.empty_text_label = ctk.CTkLabel(
            self.empty_state,
            text="A prévia do vídeo aparecerá aqui.",
            font=self.font(13, "bold"),
            text_color="#D1D5DB",
            anchor="center",
            justify="center"
        )
        self.empty_text_label.grid(row=1, column=0, sticky="ew", pady=(4, 0))

        self.controls = ctk.CTkFrame(self.frame, fg_color="transparent")
        self.controls.grid(row=2, column=0, sticky="ew", padx=15, pady=(9, 13))
        self.controls.grid_columnconfigure(2, weight=1)

        self.btn_restart = ctk.CTkButton(
            self.controls,
            text="⏮",
            command=self.restart,
            font=self.font(13, "bold"),
            width=34,
            height=32,
            corner_radius=9,
            fg_color="#FFFFFF",
            hover_color="#F2F6FB",
            text_color=self.colors["text"],
            border_width=1,
            border_color=self.colors["strong_border"],
            state="disabled"
        )
        self.btn_restart.grid(row=0, column=0, sticky="w")

        self.btn_play = ctk.CTkButton(
            self.controls,
            text="▶",
            command=self.toggle_play,
            font=self.font(13, "bold"),
            width=34,
            height=32,
            corner_radius=9,
            fg_color=self.colors["accent"],
            hover_color=self.colors["accent_hover"],
            text_color="#FFFFFF",
            state="disabled"
        )
        self.btn_play.grid(row=0, column=1, sticky="w", padx=(6, 8))

        self.seek_slider = ctk.CTkSlider(
            self.controls,
            from_=0,
            to=1,
            number_of_steps=1000,
            command=self._on_seek,
            height=16,
            fg_color="#E8EEF6",
            progress_color=self.colors["accent"],
            button_color=self.colors["accent"],
            button_hover_color=self.colors["accent_hover"],
            state="disabled"
        )
        self.seek_slider.grid(row=0, column=2, sticky="ew", padx=(0, 8))
        self.seek_slider.set(0)

        self.time_label = ctk.CTkLabel(
            self.controls,
            text="00:00 / 00:00",
            font=self.font(10, "bold"),
            text_color=self.colors["muted"],
            width=82,
            anchor="e"
        )
        self.time_label.grid(row=0, column=3, sticky="e")

    def grid(self, **kwargs):
        self.frame.grid(**kwargs)

    def set_time_change_callback(self, callback: Callable[[float, str], None]):
        self._time_change_callback = callback

    def set_playback_change_callback(self, callback: Callable[[bool], None]):
        self._playback_change_callback = callback

    def set_overlay_change_callback(self, callback: Callable[[str, NormalizedRect], None]):
        self._overlay_change_callback = callback

    def set_overlay_edit_callbacks(
        self,
        start_callback: Optional[Callable[[], None]] = None,
        end_callback: Optional[Callable[[], None]] = None
    ):
        self._overlay_edit_start_callback = start_callback
        self._overlay_edit_end_callback = end_callback

    def set_time_mapper(self, callback: Optional[Callable[[float], Optional[tuple]]]):
        self._time_mapper = callback

    def set_editing_enabled(self, enabled: bool):
        self.editing_enabled = bool(enabled)
        if self.editing_enabled:
            return

        self.cancel_blur_selection()
        if self._overlay_drag is not None:
            if self._overlay_edit_end_callback is not None:
                try:
                    self._overlay_edit_end_callback()
                except Exception:
                    pass
            self._release_pointer_grab()
        self._overlay_drag = None
        self._overlay_hover_mode = None
        self._overlay_active_mode = None
        self._set_cursor("")
        self._draw_blur_overlay()

    def show_empty(self):
        self._current_image = None
        self.blur_states = []
        self.editor_overlays = []
        self._overlay_drag = None
        self._overlay_hover_mode = None
        self._overlay_active_mode = None
        self.controls.grid_remove()
        self._show_empty_state("A prévia do vídeo aparecerá aqui.", "▷", self.font(13, "bold"))
        self._set_controls_enabled(False)
        self.time_label.configure(text="00:00 / 00:00")
        self.seek_slider.set(0)

    def load(
        self,
        media_path: str,
        duration: float = 0.0,
        rotation_degrees: int = 0,
        source_size: Optional[tuple[int, int]] = None,
    ):
        self.release_media()

        self.media_path = media_path
        self.duration = max(0.0, float(duration or 0))
        self.source_width = int((source_size or (0, 0))[0] or 0)
        self.source_height = int((source_size or (0, 0))[1] or 0)
        self.rotation_degrees = rotation_degrees if rotation_degrees in (0, 90, 180, 270) else 0
        self.blur_states = []
        self.editor_overlays = []
        self.current_time = 0.0
        self._request_id += 1
        self._hide_empty_state()
        self.controls.grid()
        self._set_controls_enabled(True)
        self._update_time_label()

        if not os.path.exists(media_path):
            self.show_unavailable("Prévia indisponível para este vídeo.")
            return

        self.request_frame(0.0)

    def set_duration(self, duration: float, refresh: bool = False):
        self.duration = max(0.0, float(duration or 0.0))
        self.current_time = max(0.0, min(self.current_time, self.duration))
        self._sync_time_controls(force=True)
        if refresh and self.media_path:
            self._invalidate_and_request_frame(self.current_time)

    def seek_to(self, seconds: float, source: str = "external", request_frame: bool = True, emit: bool = False):
        if not self.media_path:
            return

        self.current_time = max(0.0, min(float(seconds), self.duration if self.duration > 0 else float(seconds)))
        if self.is_playing and source != "playback":
            self._playback_base_time = self.current_time
            self._playback_started_at = time.monotonic()
        self._sync_time_controls(force=(not self.is_playing or source != "playback"))
        if request_frame:
            self._invalidate_and_request_frame(self.current_time)
        if emit:
            self._emit_time_change(source)

    def set_rotation(self, rotation_degrees: int):
        """Atualiza a rotação da prévia mantendo tempo e estado de reprodução."""
        if rotation_degrees not in (0, 90, 180, 270):
            rotation_degrees = 0

        if self.rotation_degrees == rotation_degrees:
            return

        was_playing = self.is_playing
        current_time = self.current_time
        self.rotation_degrees = rotation_degrees

        if self._play_after_id is not None:
            self._cancel_after(self._play_after_id)
            self._play_after_id = None

        self.current_time = current_time
        self._invalidate_and_request_frame(current_time)

        if was_playing:
            self.is_playing = True
            self.btn_play.configure(text="❚❚")
            self._playback_base_time = current_time
            self._playback_started_at = time.monotonic()

    def set_blur_states(self, blur_states: list[BlurState], refresh: bool = True):
        """Atualiza os blurs temporais ativos no instante atual."""
        self.blur_states = [state.copy() for state in blur_states if state and state.has_effect()]
        self._request_id += 1
        if self._frame_in_flight:
            self._pending_frame_seconds = self.current_time
        self._draw_blur_overlay()

        if refresh and self.media_path:
            self.request_frame(self.current_time)

    def set_editor_overlays(self, overlays: list[dict]):
        self.editor_overlays = overlays
        self._draw_blur_overlay()

    def show_unavailable(self, message: str = "Prévia indisponível para este vídeo."):
        self.pause(refresh_frame=False)
        self._current_image = None
        self.controls.grid_remove()
        self.cancel_blur_selection()
        self._show_empty_state(message, "!", self.font(12, "bold"))
        self._set_controls_enabled(False)

    def release_media(self):
        self.pause(refresh_frame=False)
        self.cancel_blur_selection()
        self._request_id += 1
        self.media_path = None
        self.duration = 0.0
        self.current_time = 0.0
        self.source_width = 0
        self.source_height = 0
        self.rotation_degrees = 0
        self.blur_states = []
        self.editor_overlays = []
        self._overlay_drag = None
        self._overlay_hover_mode = None
        self._overlay_active_mode = None
        self._frame_in_flight = False
        self._in_flight_request_id = None
        self._pending_frame_seconds = None
        if self._seek_after_id is not None:
            self._cancel_after(self._seek_after_id)
            self._seek_after_id = None

        if self._stage_resize_after_id is not None:
            self._cancel_after(self._stage_resize_after_id)
            self._stage_resize_after_id = None

    def release(self):
        self.is_destroyed = True
        self.release_media()
        self._current_image = None

    def pause_for_processing(self) -> bool:
        was_playing = self.is_playing
        self.pause(refresh_frame=False)
        return was_playing

    def toggle_play(self):
        if not self.media_path:
            return

        if self.is_playing:
            self.pause()
        else:
            self.play()

    def play(self):
        if not self.media_path or self.is_destroyed:
            return

        if self.duration > 0 and self.current_time >= self.duration:
            self.current_time = 0.0

        self.is_playing = True
        self.btn_play.configure(text="❚❚")
        self._playback_base_time = self.current_time
        self._playback_started_at = time.monotonic()
        self._reset_frame_metrics()
        self._emit_playback_change(True)
        self._schedule_next_frame(0)

    def pause(self, refresh_frame: bool = True):
        was_playing = self.is_playing
        self.is_playing = False
        try:
            self.btn_play.configure(text="▶")
        except Exception:
            pass

        if self._play_after_id is not None:
            self._cancel_after(self._play_after_id)
            self._play_after_id = None

        if was_playing:
            self._log_frame_metrics(force=True)
            self._emit_playback_change(False)
            if refresh_frame and self.media_path and not self.is_destroyed:
                self._invalidate_and_request_frame(self.current_time)

    def restart(self):
        if not self.media_path:
            return

        self.current_time = 0.0
        if self.is_playing:
            self._playback_base_time = 0.0
            self._playback_started_at = time.monotonic()
        self._sync_time_controls(force=True)
        self._emit_time_change("player")
        self._invalidate_and_request_frame(0.0)

    def toggle_mute(self):
        self.is_muted = not self.is_muted
        self.btn_mute.set_muted(self.is_muted)

    def start_blur_selection(self, callback: Callable[[NormalizedRect], None]):
        if not self.media_path or not self.editing_enabled:
            return

        self.is_selecting_blur_region = True
        self._blur_region_callback = callback
        self._selection_start = None
        self._selection_current = None
        self._set_cursor("crosshair")
        self._draw_blur_overlay()

    def cancel_blur_selection(self):
        self.is_selecting_blur_region = False
        self._blur_region_callback = None
        self._selection_start = None
        self._selection_current = None
        try:
            self._set_cursor("")
        except Exception:
            pass
        self._draw_blur_overlay()

    def _on_stage_resize(self, _event=None):
        if getattr(self, "empty_state", None) is not None:
            self._sync_empty_state_wrap()

        if not self.media_path or self.is_playing or self.is_destroyed:
            return

        if self._stage_resize_after_id is not None:
            self._cancel_after(self._stage_resize_after_id)

        self._stage_resize_after_id = self.frame.after(180, self._refresh_current_frame)

    def _refresh_current_frame(self):
        self._stage_resize_after_id = None
        self.request_frame(self.current_time)

    def request_frame(self, seconds: float):
        if not self.media_path or self.is_destroyed:
            return

        display_seconds = max(0.0, min(float(seconds), self.duration if self.duration > 0 else float(seconds)))
        if self._frame_in_flight:
            self._pending_frame_seconds = display_seconds
            self._frame_metrics["queued"] += 1
            return

        width, height = self._stage_size()
        request_id = self._request_id
        media_path, source_seconds, mapped_width, mapped_height = self._map_timeline_time(display_seconds)
        rotation_degrees = self.rotation_degrees
        blur_states = [state.copy() for state in self.blur_states]
        if self.is_playing:
            blur_states = self._preview_playback_blurs(blur_states)
        source_width = mapped_width or self.source_width
        source_height = mapped_height or self.source_height
        self._frame_in_flight = True
        self._in_flight_request_id = request_id
        self._frame_metrics["started"] += 1

        thread = threading.Thread(
            target=self._extract_frame_worker,
            args=(
                media_path,
                source_seconds,
                display_seconds,
                width,
                height,
                rotation_degrees,
                blur_states,
                source_width,
                source_height,
                request_id
            ),
            daemon=True
        )
        thread.start()

    def _extract_frame_worker(
        self,
        media_path: str,
        source_seconds: float,
        display_seconds: float,
        width: int,
        height: int,
        rotation_degrees: int,
        blur_states: list[BlurState],
        source_width: int,
        source_height: int,
        request_id: int
    ):
        started_at = time.perf_counter()
        try:
            vf = self._build_filter(width, height, rotation_degrees, blur_states, source_width, source_height)
            cmd = [
                self.ffmpeg_path,
                "-v", "error",
                "-ss", f"{source_seconds:.3f}",
                "-i", media_path,
                "-an",
                "-frames:v", "1",
                "-vf", vf,
                "-f", "image2pipe",
                "-vcodec", "png",
                "-"
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=8)

            if result.returncode != 0 or not result.stdout:
                raise RuntimeError("frame unavailable")

            elapsed_ms = (time.perf_counter() - started_at) * 1000
            self._schedule_ui(
                lambda data=result.stdout, ts=display_seconds, rid=request_id, ms=elapsed_ms: self._apply_frame(data, ts, rid, ms)
            )
        except Exception:
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            self._schedule_ui(lambda rid=request_id, ms=elapsed_ms: self._handle_frame_error(rid, ms))

    def _build_filter(
        self,
        width: int,
        height: int,
        rotation_degrees: int,
        blur_states: list[BlurState],
        source_width: int,
        source_height: int
    ) -> str:
        tail_filters = [
            f"scale={width}:{height}:force_original_aspect_ratio=decrease",
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black"
        ]
        return build_video_filter(
            source_width or width,
            source_height or height,
            rotation=rotation_degrees,
            blur_states=blur_states if blur_states else None,
            tail_filters=tail_filters
        )

    def _map_timeline_time(self, seconds: float) -> tuple[str, float, int, int]:
        if self._time_mapper is not None:
            try:
                mapped = self._time_mapper(seconds)
                if mapped is not None:
                    media_path, source_seconds, *size = mapped
                    if media_path:
                        width = int(size[0]) if len(size) >= 1 and size[0] else 0
                        height = int(size[1]) if len(size) >= 2 and size[1] else 0
                        return media_path, max(0.0, float(source_seconds)), width, height
            except Exception:
                pass

        return self.media_path or "", max(0.0, float(seconds)), self.source_width, self.source_height

    def _apply_frame(self, data: bytes, seconds: float, request_id: int, elapsed_ms: float = 0.0):
        current_in_flight = request_id == self._in_flight_request_id
        if current_in_flight:
            self._frame_in_flight = False
            self._in_flight_request_id = None

        if self.is_destroyed or request_id != self._request_id:
            self._frame_metrics["dropped"] += 1
            if current_in_flight:
                self._request_pending_frame()
            return

        try:
            image = tk.PhotoImage(data=data, format="png")
            self._current_image = image
            self._hide_empty_state()
            self.image_label.delete("frame_image")
            self.image_label.create_image(0, 0, image=image, anchor="nw", tags=("frame_image",))
            self.image_label.tag_lower("frame_image")
            self._draw_blur_overlay()
            if not self.is_playing:
                self.current_time = seconds
                self._sync_time_controls(force=True)
                self._emit_time_change("player")
            else:
                self.current_time = self._playback_target_time()
                self._sync_time_controls()
        except Exception:
            self.show_unavailable()
            return

        self._frame_metrics["applied"] += 1
        self._frame_metrics["total_ms"] += max(0.0, float(elapsed_ms or 0.0))
        self._frame_metrics["max_ms"] = max(self._frame_metrics["max_ms"], float(elapsed_ms or 0.0))
        self._log_frame_metrics()

        if self._request_pending_frame():
            return

        if self.is_playing:
            target_time = self._playback_target_time()
            if self.duration > 0 and target_time >= self.duration:
                self.current_time = self.duration
                self.pause()
                self._sync_time_controls(force=True)
                self._emit_time_change("player")
            else:
                delay_ms = max(10, int(self.FRAME_INTERVAL_MS - float(elapsed_ms or 0.0)))
                self._schedule_next_frame(delay_ms)

    def _show_empty_state(self, text: str, icon: str, font):
        self.image_label.delete("all")
        self.empty_icon_label.configure(text=icon)
        self.empty_text_label.configure(text=text, font=font)
        self._sync_empty_state_wrap()
        self.empty_state.place(relx=0.5, rely=0.5, anchor="center")
        self.empty_state.lift()

    def _hide_empty_state(self):
        try:
            self.empty_state.place_forget()
        except Exception:
            pass

    def _sync_empty_state_wrap(self):
        try:
            width, _height = self._stage_size()
            self.empty_text_label.configure(wraplength=max(180, min(320, width - 36)))
        except Exception:
            pass

    def _show_canvas_text(self, text: str, font):
        icon, message = ("▷", text)
        if "\n" in text:
            icon, message = text.split("\n", 1)
        self._show_empty_state(message, icon, font)

    def _on_blur_selection_press(self, event):
        if not self.editing_enabled:
            return

        if not self.is_selecting_blur_region:
            self._start_overlay_drag(event)
            return

        point = self._clamp_to_video_rect(event.x, event.y)
        if point is None:
            return

        self._selection_start = point
        self._selection_current = point
        self._draw_blur_overlay()

    def _on_blur_selection_drag(self, event):
        if not self.editing_enabled and self._overlay_drag is None:
            return

        if not self.is_selecting_blur_region or self._selection_start is None:
            self._drag_overlay(event)
            return

        point = self._clamp_to_video_rect(event.x, event.y)
        if point is None:
            return

        self._selection_current = point
        self._draw_blur_overlay()

    def _on_blur_selection_release(self, event):
        if not self.editing_enabled and self._overlay_drag is None:
            return

        if not self.is_selecting_blur_region or self._selection_start is None:
            self._finish_overlay_drag(event)
            return

        point = self._clamp_to_video_rect(event.x, event.y)
        if point is None:
            self.cancel_blur_selection()
            return

        self._selection_current = point
        rect = self._selection_to_region()
        callback = self._blur_region_callback
        self.cancel_blur_selection()

        if rect is not None and callback is not None:
            callback(rect)

    def _start_overlay_drag(self, event):
        if self._overlay_change_callback is None or not self.editing_enabled or self.is_playing:
            return

        selected = self._selected_overlay()
        if selected is None:
            return

        canvas_rect = self._region_to_canvas_rect(selected["region"])
        if canvas_rect is None:
            return

        mode = self._hit_test_blur_handle(event.x, event.y, canvas_rect)
        if mode == "outside":
            return

        if self._overlay_edit_start_callback is not None:
            try:
                self._overlay_edit_start_callback()
            except Exception:
                pass
        self._set_cursor(self._cursor_for_mode(mode, dragging=True))
        self._overlay_active_mode = mode
        self._overlay_hover_mode = mode
        try:
            self.image_label.grab_set()
        except Exception:
            pass

        self._overlay_drag = {
            "id": selected["id"],
            "mode": mode,
            "start": (event.x, event.y),
            "region": selected["region"].clamped(),
        }
        self._draw_blur_overlay()

    def _drag_overlay(self, event):
        if self._overlay_drag is None:
            return

        content = self._video_content_rect()
        if content is None:
            return

        offset_x, offset_y, content_width, content_height = content
        start_x, start_y = self._overlay_drag["start"]
        delta_x = (float(event.x) - start_x) / content_width
        delta_y = (float(event.y) - start_y) / content_height
        original = self._overlay_drag["region"]
        mode = self._overlay_drag["mode"]

        if mode == "move":
            rect = NormalizedRect(
                max(0.0, min(1.0 - original.width, original.x + delta_x)),
                max(0.0, min(1.0 - original.height, original.y + delta_y)),
                original.width,
                original.height,
            )
        else:
            rect = self._resize_region(original, mode, delta_x, delta_y)

        rect = rect.clamped()
        self._update_overlay_region(self._overlay_drag["id"], rect)
        try:
            self._overlay_change_callback(self._overlay_drag["id"], rect)
        except Exception:
            pass
        self._draw_blur_overlay()

    def _finish_overlay_drag(self, event):
        if self._overlay_drag is None:
            return
        self._drag_overlay(event)
        if self._overlay_edit_end_callback is not None:
            try:
                self._overlay_edit_end_callback()
            except Exception:
                pass
        self._overlay_drag = None
        self._overlay_active_mode = None
        self._release_pointer_grab()
        self._on_overlay_motion(event)

    def _resize_region(self, original: NormalizedRect, mode: str, delta_x: float, delta_y: float) -> NormalizedRect:
        min_size = 0.01
        left = original.x
        top = original.y
        right = original.x + original.width
        bottom = original.y + original.height

        if "left" in mode or "nw" in mode or "sw" in mode:
            left = max(0.0, min(right - min_size, left + delta_x))
        if "right" in mode or "ne" in mode or "se" in mode:
            right = min(1.0, max(left + min_size, right + delta_x))
        if "top" in mode or "nw" in mode or "ne" in mode:
            top = max(0.0, min(bottom - min_size, top + delta_y))
        if "bottom" in mode or "sw" in mode or "se" in mode:
            bottom = min(1.0, max(top + min_size, bottom + delta_y))

        return NormalizedRect(left, top, right - left, bottom - top)

    def _hit_test_blur_handle(
        self,
        x: float,
        y: float,
        canvas_rect: tuple[float, float, float, float]
    ) -> str:
        left, top, right, bottom = canvas_rect
        corner_hit = self.HANDLE_CORNER_HIT_RADIUS
        side_hit = self.HANDLE_SIDE_HIT_RADIUS
        edge_hit = self.HANDLE_EDGE_HIT_RADIUS
        if not (
            left - corner_hit <= x <= right + corner_hit
            and top - corner_hit <= y <= bottom + corner_hit
        ):
            return "outside"

        for mode, center in self._overlay_handle_points(canvas_rect, corners_only=True).items():
            cx, cy = center
            if abs(x - cx) <= corner_hit and abs(y - cy) <= corner_hit:
                return mode

        for mode, center in self._overlay_handle_points(canvas_rect, sides_only=True).items():
            cx, cy = center
            if abs(x - cx) <= side_hit and abs(y - cy) <= side_hit:
                return mode

        if top + corner_hit < y < bottom - corner_hit:
            if abs(x - left) <= edge_hit:
                return "left"
            if abs(x - right) <= edge_hit:
                return "right"
        if left + corner_hit < x < right - corner_hit:
            if abs(y - top) <= edge_hit:
                return "top"
            if abs(y - bottom) <= edge_hit:
                return "bottom"
        if left <= x <= right and top <= y <= bottom:
            return "move"
        return "outside"

    def _on_overlay_motion(self, event):
        if not self.editing_enabled or self.is_playing:
            self._set_overlay_hover_mode(None)
            self._set_cursor("")
            return
        if self.is_selecting_blur_region:
            self._set_cursor("crosshair")
            return
        if self._overlay_drag is not None:
            self._set_cursor(self._cursor_for_mode(self._overlay_drag.get("mode", "move"), dragging=True))
            return

        selected = self._selected_overlay()
        if selected is None:
            self._set_overlay_hover_mode(None)
            self._set_cursor("")
            return

        canvas_rect = self._region_to_canvas_rect(selected["region"])
        if canvas_rect is None:
            self._set_overlay_hover_mode(None)
            self._set_cursor("")
            return

        mode = self._hit_test_blur_handle(event.x, event.y, canvas_rect)
        self._set_overlay_hover_mode(None if mode == "outside" else mode)
        self._set_cursor(self._cursor_for_mode(mode) if mode != "outside" else "")

    def _on_overlay_leave(self, _event):
        if self._overlay_drag is None:
            self._set_overlay_hover_mode(None)
        self._set_cursor("")

    def _set_overlay_hover_mode(self, mode: Optional[str]):
        if self._overlay_hover_mode == mode:
            return
        self._overlay_hover_mode = mode
        self._draw_blur_overlay()

    def _cursor_for_mode(self, mode: Optional[str], dragging: bool = False) -> str:
        if mode in ("left", "right"):
            return "sb_h_double_arrow"
        if mode in ("top", "bottom"):
            return "sb_v_double_arrow"
        if mode in ("nw", "se", "ne", "sw"):
            return "sizing"
        if mode == "move":
            return "fleur"
        return ""

    def _set_cursor(self, cursor: str):
        try:
            self.image_label.configure(cursor=cursor)
        except Exception:
            try:
                self.image_label.configure(cursor="" if cursor else cursor)
            except Exception:
                pass

    def _selection_to_region(self) -> Optional[NormalizedRect]:
        if self._selection_start is None or self._selection_current is None:
            return None

        content = self._video_content_rect()
        if content is None:
            return None

        offset_x, offset_y, content_width, content_height = content
        start_x, start_y = self._selection_start
        end_x, end_y = self._selection_current
        left = min(start_x, end_x)
        top = min(start_y, end_y)
        right = max(start_x, end_x)
        bottom = max(start_y, end_y)

        if right - left < 8 or bottom - top < 8:
            return None

        rect = NormalizedRect(
            x=(left - offset_x) / content_width,
            y=(top - offset_y) / content_height,
            width=(right - left) / content_width,
            height=(bottom - top) / content_height
        ).clamped()

        return rect if rect.is_usable() else None

    def _clamp_to_video_rect(self, x: float, y: float) -> Optional[tuple[float, float]]:
        content = self._video_content_rect()
        if content is None:
            return None

        offset_x, offset_y, content_width, content_height = content
        clamped_x = max(offset_x, min(offset_x + content_width, float(x)))
        clamped_y = max(offset_y, min(offset_y + content_height, float(y)))
        return clamped_x, clamped_y

    def _video_content_rect(self) -> Optional[tuple[float, float, float, float]]:
        stage_width, stage_height = self._stage_size()
        source_width, source_height = rotated_dimensions(
            self.source_width,
            self.source_height,
            self.rotation_degrees
        )

        if source_width <= 0 or source_height <= 0:
            return None

        scale = min(stage_width / source_width, stage_height / source_height)
        content_width = source_width * scale
        content_height = source_height * scale
        offset_x = (stage_width - content_width) / 2
        offset_y = (stage_height - content_height) / 2
        return offset_x, offset_y, content_width, content_height

    def _region_to_canvas_rect(self, region: NormalizedRect) -> Optional[tuple[float, float, float, float]]:
        content = self._video_content_rect()
        if content is None:
            return None

        rect = region.clamped()
        offset_x, offset_y, content_width, content_height = content
        left = offset_x + rect.x * content_width
        top = offset_y + rect.y * content_height
        right = left + rect.width * content_width
        bottom = top + rect.height * content_height
        return left, top, right, bottom

    def _draw_blur_overlay(self):
        try:
            self.image_label.delete("blur_overlay")
            self.image_label.delete("selection_overlay")
            self.image_label.delete("editor_overlay")
            self.image_label.delete("blur_instruction")
        except Exception:
            return

        if self.editor_overlays:
            for overlay in self.editor_overlays:
                region = overlay.get("region")
                if region is None:
                    continue
                canvas_rect = self._region_to_canvas_rect(region)
                if canvas_rect is None:
                    continue
                selected = bool(overlay.get("selected"))
                color = self.colors["accent"] if selected else "#9AC8FF"
                self._draw_region_rect(
                    canvas_rect,
                    "editor_overlay",
                    color,
                    selected=selected,
                    label=overlay.get("name", ""),
                    hover_mode=self._overlay_hover_mode if selected else None,
                    active_mode=self._overlay_active_mode if selected else None,
                )
        if self.is_selecting_blur_region and self._selection_start and self._selection_current:
            start_x, start_y = self._selection_start
            end_x, end_y = self._selection_current
            canvas_rect = (min(start_x, end_x), min(start_y, end_y), max(start_x, end_x), max(start_y, end_y))
            self._draw_region_rect(canvas_rect, "selection_overlay", "#FFFFFF")
        elif self.is_selecting_blur_region:
            self._draw_blur_instruction()

    def _draw_blur_instruction(self):
        text = "Clique e arraste sobre o vídeo para desenhar a área que deseja desfocar."
        width, height = self._stage_size()
        box_width = min(max(280, len(text) * 5), max(280, width - 36))
        x = max(18, (width - box_width) / 2)
        y = max(18, height - 58)
        self.image_label.create_rectangle(
            x,
            y,
            x + box_width,
            y + 34,
            fill="#111827",
            outline="",
            tags=("blur_instruction",),
        )
        self.image_label.create_text(
            x + 12,
            y + 17,
            text=text,
            fill="#FFFFFF",
            font=self.font(10, "bold"),
            anchor="w",
            tags=("blur_instruction",),
        )

    def _draw_region_rect(
        self,
        canvas_rect: tuple[float, float, float, float],
        tag: str,
        color: str,
        selected: bool = False,
        label: str = "",
        hover_mode: Optional[str] = None,
        active_mode: Optional[str] = None,
    ):
        left, top, right, bottom = canvas_rect
        self.image_label.create_rectangle(
            left,
            top,
            right,
            bottom,
            outline=color,
            width=3 if selected else 2,
            dash=(5, 3),
            tags=(tag,)
        )
        self.image_label.create_rectangle(
            left + 3,
            top + 3,
            right - 3,
            bottom - 3,
            outline="#FFFFFF",
            width=1,
            tags=(tag,)
        )
        if label:
            self.image_label.create_text(
                left + 6,
                max(12, top - 10),
                text=label,
                fill="#FFFFFF",
                font=self.font(9, "bold"),
                anchor="w",
                tags=(tag,)
            )
        if selected:
            points = self._overlay_handle_points(canvas_rect)
            for mode, (x, y) in points.items():
                if active_mode == mode:
                    handle_size = self.HANDLE_ACTIVE_SIZE
                    outline = "#FFFFFF"
                    fill = color
                    width = 2
                elif hover_mode == mode:
                    handle_size = self.HANDLE_HOVER_SIZE
                    outline = color
                    fill = "#FFFFFF"
                    width = 2
                else:
                    handle_size = self.HANDLE_VISIBLE_SIZE
                    outline = color
                    fill = "#FFFFFF"
                    width = 1
                self.image_label.create_rectangle(
                    x - handle_size / 2,
                    y - handle_size / 2,
                    x + handle_size / 2,
                    y + handle_size / 2,
                    fill=fill,
                    outline=outline,
                    width=width,
                    tags=(tag,),
                )
            self.image_label.create_oval(
                (left + right) / 2 - 3,
                (top + bottom) / 2 - 3,
                (left + right) / 2 + 3,
                (top + bottom) / 2 + 3,
                fill=color,
                outline="#FFFFFF",
                tags=(tag,),
            )

    def _overlay_handle_points(
        self,
        canvas_rect: tuple[float, float, float, float],
        corners_only: bool = False,
        sides_only: bool = False,
    ) -> dict[str, tuple[float, float]]:
        left, top, right, bottom = canvas_rect
        center_x = (left + right) / 2
        center_y = (top + bottom) / 2
        corners = {
            "nw": (left, top),
            "ne": (right, top),
            "sw": (left, bottom),
            "se": (right, bottom),
        }
        sides = {
            "top": (center_x, top),
            "bottom": (center_x, bottom),
            "left": (left, center_y),
            "right": (right, center_y),
        }
        if corners_only:
            return corners
        if sides_only:
            return sides
        return {**corners, **sides}

    def _selected_overlay(self) -> Optional[dict]:
        for overlay in self.editor_overlays:
            if overlay.get("selected"):
                region = overlay.get("region")
                if isinstance(region, NormalizedRect):
                    return overlay
        return None

    def _update_overlay_region(self, overlay_id: str, region: NormalizedRect):
        for overlay in self.editor_overlays:
            if overlay.get("id") == overlay_id:
                overlay["region"] = region.clamped()
                return

    def _handle_frame_error(self, request_id: int, elapsed_ms: float = 0.0):
        current_in_flight = request_id == self._in_flight_request_id
        if current_in_flight:
            self._frame_in_flight = False
            self._in_flight_request_id = None
        if self.is_destroyed or request_id != self._request_id:
            self._frame_metrics["dropped"] += 1
            if current_in_flight:
                self._request_pending_frame()
            return

        self._frame_metrics["errors"] += 1
        self._frame_metrics["total_ms"] += max(0.0, float(elapsed_ms or 0.0))
        self._frame_metrics["max_ms"] = max(self._frame_metrics["max_ms"], float(elapsed_ms or 0.0))
        self._log_frame_metrics()
        self.show_unavailable()

    def _schedule_next_frame(self, delay_ms: int, seconds: Optional[float] = None):
        if self._play_after_id is not None:
            self._cancel_after(self._play_after_id)

        target_time = self._playback_target_time() if seconds is None and self.is_playing else (self.current_time if seconds is None else seconds)
        self._play_after_id = self.frame.after(
            delay_ms,
            lambda: self.request_frame(self._playback_target_time() if self.is_playing else target_time)
        )

    def _on_seek(self, value):
        if not self.media_path or self.duration <= 0:
            return

        self.current_time = float(value) * self.duration
        if self.is_playing:
            self._playback_base_time = self.current_time
            self._playback_started_at = time.monotonic()
        self._sync_time_controls(force=True)
        self._emit_time_change("player")

        if self._seek_after_id is not None:
            self._cancel_after(self._seek_after_id)

        self._seek_after_id = self.frame.after(140, self._apply_seek)

    def _apply_seek(self):
        self._seek_after_id = None
        self._invalidate_and_request_frame(self.current_time)

    def _sync_time_controls(self, force: bool = False):
        now = time.monotonic()
        if not force and self.is_playing and (now - self._last_time_label_update_at) * 1000 < self.TIME_LABEL_INTERVAL_MS:
            return

        if self.duration > 0:
            self.seek_slider.set(max(0.0, min(1.0, self.current_time / self.duration)))
        else:
            self.seek_slider.set(0)
        self.time_label.configure(
            text=f"{self._format_time(self.current_time)} / {self._format_time(self.duration)}"
        )
        self._last_time_label_update_at = now

    def _sync_seek_from_time(self):
        self._sync_time_controls(force=True)

    def _update_time_label(self):
        self._sync_time_controls(force=True)

    def _set_controls_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self.btn_play.configure(state=state)
        self.btn_restart.configure(state=state)
        self.seek_slider.configure(state=state)

    def _stage_size(self) -> tuple[int, int]:
        self.stage.update_idletasks()
        width = max(220, self.stage.winfo_width())
        height = max(120, self.stage.winfo_height())
        return width, height

    def _cancel_after(self, after_id):
        try:
            self.frame.after_cancel(after_id)
        except Exception:
            pass

    def _schedule_ui(self, callback):
        if self.is_destroyed:
            return

        try:
            self.frame.after(0, callback)
        except Exception:
            pass

    def _playback_target_time(self) -> float:
        if not self.is_playing:
            return self.current_time

        elapsed = time.monotonic() - self._playback_started_at
        target = self._playback_base_time + max(0.0, elapsed)
        if self.duration > 0:
            return max(0.0, min(self.duration, target))
        return max(0.0, target)

    def _preview_playback_blurs(self, blur_states: list[BlurState]) -> list[BlurState]:
        optimized = []
        for state in blur_states:
            clone = state.copy()
            clone.intensity = min(float(clone.intensity or 0.0), 0.72)
            optimized.append(clone)
        return optimized

    def _invalidate_and_request_frame(self, seconds: float):
        target = max(0.0, min(float(seconds), self.duration if self.duration > 0 else float(seconds)))
        self._request_id += 1
        if self._frame_in_flight:
            self._pending_frame_seconds = target
            self._frame_metrics["queued"] += 1
            return
        self.request_frame(target)

    def _request_pending_frame(self) -> bool:
        pending = self._pending_frame_seconds
        self._pending_frame_seconds = None
        if pending is None or self.is_destroyed or not self.media_path:
            return False

        self.request_frame(pending)
        return True

    def _reset_frame_metrics(self):
        self._metrics_window_started_at = time.perf_counter()
        self._frame_metrics = {
            "started": 0,
            "applied": 0,
            "dropped": 0,
            "errors": 0,
            "queued": 0,
            "total_ms": 0.0,
            "max_ms": 0.0,
        }

    def _log_frame_metrics(self, force: bool = False):
        now = time.perf_counter()
        elapsed = max(0.001, now - self._metrics_window_started_at)
        if not force and elapsed < 5.0:
            return

        metrics = self._frame_metrics
        completed = metrics["applied"] + metrics["errors"]
        if completed <= 0 and not force:
            return

        avg_ms = metrics["total_ms"] / max(1, completed)
        fps = metrics["applied"] / elapsed
        print(
            "[preview] "
            f"fps={fps:.1f} avg_frame={avg_ms:.1f}ms max_frame={metrics['max_ms']:.1f}ms "
            f"started={metrics['started']} applied={metrics['applied']} "
            f"queued_latest={metrics['queued']} dropped={metrics['dropped']} errors={metrics['errors']}"
        )
        self._reset_frame_metrics()

    def _release_pointer_grab(self):
        try:
            self.image_label.grab_release()
        except Exception:
            pass

    def _emit_time_change(self, source: str):
        if self._time_change_callback is None:
            return
        try:
            self._time_change_callback(self.current_time, source)
        except Exception:
            pass

    def _emit_playback_change(self, is_playing: bool):
        if self._playback_change_callback is None:
            return
        try:
            self._playback_change_callback(is_playing)
        except Exception:
            pass

    def _format_time(self, seconds: float) -> str:
        seconds = max(0, int(seconds or 0))
        minutes, secs = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)

        if hours:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"
