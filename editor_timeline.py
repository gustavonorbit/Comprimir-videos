"""Workspace temporal do editor desktop."""

from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk
import tkinter as tk

from editor_state import BlurFilter, EditorState, MIN_FILTER_DURATION, SELECTED_SEGMENT, VideoSegment


class EditorTimeline:
    RULER_HEIGHT = 38
    LABEL_WIDTH = 74
    RIGHT_PAD = 14
    TRACK_HEIGHT = 26
    TRACK_GAP = 10
    VIDEO_TOP = 52

    def __init__(
        self,
        parent,
        editor_state: EditorState,
        font: Callable,
        colors: dict,
        on_add_blur: Callable[[], None],
        on_seek: Callable[[float, str], None],
        on_filter_select: Callable[[str], None],
        on_filter_changed: Callable[[str], None],
        on_filter_delete: Callable[[str], None],
        on_filter_duplicate: Callable[[str], None],
        on_segment_select: Callable[[str], None],
        on_segment_delete: Callable[[str], None],
        on_segment_duplicate: Callable[[str], None],
        on_segment_move: Callable[[str, int], None],
    ):
        self.editor_state = editor_state
        self.font = font
        self.colors = colors
        self.on_add_blur = on_add_blur
        self.on_seek = on_seek
        self.on_filter_select = on_filter_select
        self.on_filter_changed = on_filter_changed
        self.on_filter_delete = on_filter_delete
        self.on_filter_duplicate = on_filter_duplicate
        self.on_segment_select = on_segment_select
        self.on_segment_delete = on_segment_delete
        self.on_segment_duplicate = on_segment_duplicate
        self.on_segment_move = on_segment_move

        self._drag: Optional[dict] = None
        self._block_regions: dict[str, tuple[float, float, float, float]] = {}
        self._segment_regions: dict[str, tuple[float, float, float, float]] = {}
        self._active_ids: set[str] = set()
        self._snap_feedback_time: Optional[float] = None
        self._drag_feedback: Optional[tuple[str, float, float]] = None
        self._updating_inspector = False
        self._enabled = True

        self.frame = ctk.CTkFrame(
            parent,
            fg_color=colors["card"],
            corner_radius=14,
            border_width=1,
            border_color=colors["border"],
        )
        self.frame.grid_columnconfigure(0, weight=1)
        self.frame.grid_rowconfigure(1, weight=1)

        self._build_ui()
        self.refresh()

    def _build_ui(self):
        toolbar = ctk.CTkFrame(self.frame, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=14, pady=(13, 9))
        toolbar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            toolbar,
            text="Editor",
            font=self.font(15, "bold"),
            text_color=self.colors["text"],
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        self.time_label = ctk.CTkLabel(
            toolbar,
            text="00:00 / 00:00",
            font=self.font(10, "bold"),
            text_color=self.colors["muted"],
            anchor="e",
        )
        self.time_label.grid(row=0, column=1, sticky="e", padx=(12, 10))

        self.btn_add_blur = ctk.CTkButton(
            toolbar,
            text="Adicionar blur",
            command=self.on_add_blur,
            font=self.font(12, "bold"),
            width=116,
            height=32,
            corner_radius=10,
            fg_color=self.colors["accent"],
            hover_color=self.colors["accent_hover"],
            text_color="#FFFFFF",
        )
        self.btn_add_blur.grid(row=0, column=2, sticky="e")

        canvas_wrap = ctk.CTkFrame(self.frame, fg_color="#F8FAFC", corner_radius=12)
        canvas_wrap.grid(row=1, column=0, sticky="nsew", padx=14)
        canvas_wrap.grid_columnconfigure(0, weight=1)
        canvas_wrap.grid_rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            canvas_wrap,
            bg="#F8FAFC",
            highlightthickness=0,
            bd=0,
            height=190,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.v_scrollbar = ctk.CTkScrollbar(canvas_wrap, orientation="vertical", command=self.canvas.yview)
        self.v_scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=self.v_scrollbar.set)
        self.canvas.bind("<Configure>", lambda _event: self.refresh(redraw_inspector=False))
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", lambda _event: self.canvas.configure(cursor=""))

        self.inspector = ctk.CTkFrame(self.frame, fg_color="transparent")
        self.inspector.grid(row=2, column=0, sticky="ew", padx=14, pady=(9, 13))
        for column in range(6):
            self.inspector.grid_columnconfigure(column, weight=1 if column in (1, 3) else 0)

        self.inspector_title = ctk.CTkLabel(
            self.inspector,
            text="Nenhum filtro selecionado",
            font=self.font(12, "bold"),
            text_color=self.colors["text"],
            anchor="w",
        )
        self.inspector_title.grid(row=0, column=0, columnspan=6, sticky="ew")

        self.start_entry = ctk.CTkEntry(
            self.inspector,
            height=30,
            width=78,
            font=self.font(11),
            corner_radius=9,
            border_color=self.colors["strong_border"],
        )
        self.end_entry = ctk.CTkEntry(
            self.inspector,
            height=30,
            width=78,
            font=self.font(11),
            corner_radius=9,
            border_color=self.colors["strong_border"],
        )
        self.start_caption = ctk.CTkLabel(
            self.inspector,
            text="Início",
            font=self.font(10, "bold"),
            text_color=self.colors["muted"],
            anchor="w",
        )
        self.end_caption = ctk.CTkLabel(
            self.inspector,
            text="Fim",
            font=self.font(10, "bold"),
            text_color=self.colors["muted"],
            anchor="w",
        )
        self.region_label = ctk.CTkLabel(
            self.inspector,
            text="Região: --",
            font=self.font(10),
            text_color=self.colors["muted"],
            anchor="w",
        )
        self.motion_label = ctk.CTkLabel(
            self.inspector,
            text="Movimento: Fixo",
            font=self.font(10),
            text_color=self.colors["muted"],
            anchor="w",
        )
        self.btn_duplicate = ctk.CTkButton(
            self.inspector,
            text="Duplicar",
            command=self._duplicate_selected,
            font=self.font(11, "bold"),
            height=30,
            width=74,
            corner_radius=9,
            fg_color="#FFFFFF",
            hover_color="#F2F6FB",
            text_color=self.colors["text"],
            border_width=1,
            border_color=self.colors["strong_border"],
        )
        self.btn_delete = ctk.CTkButton(
            self.inspector,
            text="Excluir",
            command=self._delete_selected,
            font=self.font(11, "bold"),
            height=30,
            width=66,
            corner_radius=9,
            fg_color="#FFFFFF",
            hover_color="#FFF2F1",
            text_color="#FF3B30",
            border_width=1,
            border_color="#FFD2CE",
        )

        for widget in (self.start_entry, self.end_entry):
            widget.bind("<Return>", self._commit_entry_times)
            widget.bind("<FocusOut>", self._commit_entry_times)

        self._grid_inspector_fields(False)

    def grid(self, **kwargs):
        self.frame.grid(**kwargs)

    def refresh(self, redraw_inspector: bool = True):
        self._draw_timeline()
        if redraw_inspector:
            self._draw_inspector()

    def update_playhead(self):
        active_ids = {
            item.id for item in self.editor_state.filters
            if item.contains(self.editor_state.playback.current_time)
        }
        if active_ids != self._active_ids:
            self._draw_timeline()
        else:
            self.canvas.delete("playhead")
            self._draw_playhead()
        self._update_time_label()

    def set_enabled(self, enabled: bool):
        self._enabled = enabled
        state = "normal" if enabled else "disabled"
        self.btn_add_blur.configure(state=state)
        self.start_entry.configure(state=state)
        self.end_entry.configure(state=state)
        self.btn_duplicate.configure(state=state)
        self.btn_delete.configure(state=state)
        self.refresh(redraw_inspector=True)

    def _draw_timeline(self):
        self.canvas.delete("all")
        self._block_regions.clear()
        self._segment_regions.clear()
        self._active_ids = {
            item.id for item in self.editor_state.filters
            if item.contains(self.editor_state.playback.current_time)
        }

        width = max(320, self.canvas.winfo_width())
        height = max(160, self.canvas.winfo_height())
        content_height = max(height, self._content_height())
        self.canvas.create_rectangle(0, 0, width, content_height, fill="#F8FAFC", outline="")

        self._draw_ruler(width)
        self._draw_video_track(width)
        self._draw_filter_tracks(width)
        self._draw_playhead()
        self._draw_snap_feedback(width)
        self._draw_drag_feedback()
        self.canvas.configure(scrollregion=(0, 0, width, content_height))
        self._update_time_label()

    def _draw_ruler(self, width: int):
        left, right = self._timeline_bounds(width)
        y = 18
        self.canvas.create_text(
            10,
            y,
            text="Tempo",
            fill=self.colors["muted"],
            font=self._tk_font(10, "bold"),
            anchor="w",
        )
        self.canvas.create_line(left, self.RULER_HEIGHT, right, self.RULER_HEIGHT, fill="#D5DDEC", width=1)
        for tick in self._tick_times():
            x = self._time_to_x(tick, width)
            major = tick in (0.0, self.editor_state.playback.duration)
            self.canvas.create_line(
                x,
                self.RULER_HEIGHT - (12 if major else 8),
                x,
                self.RULER_HEIGHT + 7,
                fill="#B9C4D5" if major else "#D5DDEC",
                width=1,
            )
            self.canvas.create_text(
                x,
                y,
                text=self._format_time(tick),
                fill=self.colors["muted"],
                font=self._tk_font(9, "bold" if major else None),
                anchor="center",
            )

    def _draw_video_track(self, width: int):
        left, right = self._timeline_bounds(width)
        top = self.VIDEO_TOP
        bottom = top + self.TRACK_HEIGHT
        self.canvas.create_text(
            10,
            (top + bottom) / 2,
            text="Vídeo",
            fill=self.colors["text"],
            font=self._tk_font(10, "bold"),
            anchor="w",
        )
        self.canvas.create_rectangle(left, top, right, bottom, fill="#FFFFFF", outline="#E4E9F1", width=1)

        if not self.editor_state.segments:
            self.canvas.create_text(
                left + 8,
                (top + bottom) / 2,
                text="Nenhum clipe carregado",
                fill=self.colors["muted"],
                font=self._tk_font(10),
                anchor="w",
            )
            return

        for index, segment in enumerate(self.editor_state.segments, start=1):
            block_left = self._time_to_x(segment.timeline_start, width)
            block_right = self._time_to_x(segment.timeline_end, width)
            if block_right - block_left < 2:
                block_right = block_left + 2

            selected = (
                self.editor_state.playback.selected_item_type == SELECTED_SEGMENT
                and self.editor_state.playback.selected_item_id == segment.id
            )
            fill = "#EAF4FF" if selected else "#F3F9FF"
            outline = self.colors["accent"] if selected else "#B8D7FF"
            self.canvas.create_rectangle(
                block_left,
                top + 3,
                block_right,
                bottom - 3,
                fill=fill,
                outline=outline,
                width=2 if selected else 1,
                tags=(f"segment_{segment.id}", "segment_block"),
            )
            self.canvas.create_line(block_left, top + 6, block_left, bottom - 6, fill=outline, width=1)
            self.canvas.create_line(block_right, top + 6, block_right, bottom - 6, fill=outline, width=1)
            self.canvas.create_text(
                (block_left + block_right) / 2,
                (top + bottom) / 2,
                text=f"S{index}",
                fill=self.colors["accent"] if selected else self.colors["muted"],
                font=self._tk_font(9, "bold"),
                anchor="center",
            )
            self._segment_regions[segment.id] = (block_left, top, block_right, bottom)

    def _draw_filter_tracks(self, width: int):
        left, right = self._timeline_bounds(width)
        top = self.VIDEO_TOP + self.TRACK_HEIGHT + self.TRACK_GAP

        if not self.editor_state.filters:
            self.canvas.create_text(
                left,
                top + 18,
                text="Clique em + Blur e desenhe uma área na prévia.",
                fill=self.colors["muted"],
                font=self._tk_font(10),
                anchor="w",
            )
            return

        for index, item in enumerate(self.editor_state.filters):
            row_top = top + index * (self.TRACK_HEIGHT + self.TRACK_GAP)
            row_bottom = row_top + self.TRACK_HEIGHT
            selected = item.id == self.editor_state.playback.selected_filter_id
            active = item.id in self._active_ids

            self.canvas.create_text(
                10,
                (row_top + row_bottom) / 2,
                text=item.name,
                fill=self.colors["text"] if selected else self.colors["muted"],
                font=self._tk_font(10, "bold" if selected else None),
                anchor="w",
            )
            self.canvas.create_rectangle(left, row_top, right, row_bottom, fill="#FFFFFF", outline="#E4E9F1")

            block_left = self._time_to_x(item.start_time, width)
            block_right = self._time_to_x(item.end_time, width)
            fill = "#007AFF" if active else "#DDEEFF"
            outline = "#005FC8" if selected else "#9AC8FF"
            text_color = "#FFFFFF" if active else self.colors["accent"]
            self.canvas.create_rectangle(
                block_left,
                row_top + 3,
                block_right,
                row_bottom - 3,
                fill=fill,
                outline=outline,
                width=2 if selected else 1,
                tags=(f"filter_{item.id}", "filter_block"),
            )
            self.canvas.create_rectangle(block_left, row_top + 3, block_left + 6, row_bottom - 3, fill=outline, outline="")
            self.canvas.create_rectangle(block_right - 6, row_top + 3, block_right, row_bottom - 3, fill=outline, outline="")
            self.canvas.create_text(
                (block_left + block_right) / 2,
                (row_top + row_bottom) / 2,
                text=self._format_time_span(item.start_time, item.end_time),
                fill=text_color,
                font=self._tk_font(9, "bold"),
                anchor="center",
            )
            self._block_regions[item.id] = (block_left, row_top, block_right, row_bottom)

    def _draw_playhead(self):
        width = max(320, self.canvas.winfo_width())
        height = max(160, self.canvas.winfo_height())
        x = self._time_to_x(self.editor_state.playback.current_time, width)
        self.canvas.create_line(x, self.RULER_HEIGHT - 14, x, height - 10, fill="#FF3B30", width=2, tags=("playhead",))
        self.canvas.create_oval(x - 4, self.RULER_HEIGHT - 18, x + 4, self.RULER_HEIGHT - 10, fill="#FF3B30", outline="", tags=("playhead",))

    def _draw_snap_feedback(self, width: int):
        if self._snap_feedback_time is None:
            return
        height = max(160, self.canvas.winfo_height())
        x = self._time_to_x(self._snap_feedback_time, width)
        self.canvas.create_line(
            x,
            self.RULER_HEIGHT - 16,
            x,
            height - 8,
            fill="#34C759",
            width=2,
            dash=(4, 3),
            tags=("snap_feedback",),
        )

    def _draw_drag_feedback(self):
        if self._drag_feedback is None:
            return

        text, x, y = self._drag_feedback
        text_width = max(90, len(text) * 6 + 16)
        self.canvas.create_rectangle(
            x,
            y,
            x + text_width,
            y + 24,
            fill="#111827",
            outline="",
            tags=("drag_feedback",),
        )
        self.canvas.create_text(
            x + 8,
            y + 12,
            text=text,
            fill="#FFFFFF",
            font=self._tk_font(9, "bold"),
            anchor="w",
            tags=("drag_feedback",),
        )

    def _draw_inspector(self):
        selected_segment = self.editor_state.selected_segment()
        if selected_segment is not None:
            self._draw_segment_inspector(selected_segment)
            return

        selected = self.editor_state.selected_filter()
        if not isinstance(selected, BlurFilter):
            self.inspector_title.configure(text="Nenhum item selecionado")
            self._grid_inspector_fields(False)
            return

        self._grid_inspector_fields(True, item_type="filter")
        self._updating_inspector = True
        self.inspector_title.configure(text=selected.name)
        rect = selected.region.clamped()
        self.region_label.configure(text=f"Região: {int(rect.width * 100)}x{int(rect.height * 100)}%")
        self.motion_label.configure(text="Movimento: Fixo · ajuste a duração pela barra")
        self.btn_duplicate.configure(text="Duplicar")
        self.btn_delete.configure(text="Excluir", width=66)
        self._updating_inspector = False

    def _draw_segment_inspector(self, segment: VideoSegment):
        self._grid_inspector_fields(True, item_type="segment")
        self._updating_inspector = True
        name = segment.metadata.get("name") or f"Segmento {self.editor_state.segments.index(segment) + 1}"
        source_name = segment.source_path.replace("\\", "/").rsplit("/", 1)[-1] if segment.source_path else "--"
        self.inspector_title.configure(text=name)
        self.start_entry.configure(state="normal")
        self.end_entry.configure(state="normal")
        self._replace_entry_value(self.start_entry, self._format_time_precise(segment.timeline_start))
        self._replace_entry_value(self.end_entry, self._format_time_precise(segment.timeline_end))
        self.start_entry.configure(state="disabled")
        self.end_entry.configure(state="disabled")
        self.region_label.configure(text=f"Origem: {source_name}")
        self.motion_label.configure(
            text=f"Fonte: {self._format_time_precise(segment.source_start)}-{self._format_time_precise(segment.source_end)}"
        )
        self.btn_duplicate.configure(text="Duplicar", width=74)
        self.btn_delete.configure(text="Excluir e fechar", width=126)
        self._updating_inspector = False

    def _grid_inspector_fields(self, visible: bool, item_type: str = "filter"):
        widgets = (
            self.start_caption,
            self.end_caption,
            self.start_entry,
            self.end_entry,
            self.region_label,
            self.motion_label,
            self.btn_duplicate,
            self.btn_delete,
        )
        for widget in widgets:
            widget.grid_forget()

        if not visible:
            return

        if item_type == "segment":
            self.start_caption.grid(row=1, column=0, sticky="w", pady=(7, 0), padx=(0, 5))
            self.start_entry.grid(row=1, column=1, sticky="w", pady=(7, 0), padx=(0, 10))
            self.end_caption.grid(row=1, column=2, sticky="w", pady=(7, 0), padx=(0, 5))
            self.end_entry.grid(row=1, column=3, sticky="w", pady=(7, 0), padx=(0, 10))
            self.btn_duplicate.grid(row=1, column=4, sticky="e", pady=(7, 0), padx=(0, 7))
            self.btn_delete.grid(row=1, column=5, sticky="e", pady=(7, 0))
        else:
            self.btn_duplicate.grid(row=1, column=4, sticky="e", pady=(7, 0), padx=(0, 7))
            self.btn_delete.grid(row=1, column=5, sticky="e", pady=(7, 0))

        row = 2 if item_type == "segment" else 1
        self.region_label.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(8, 0), padx=(0, 10))
        self.motion_label.grid(row=row, column=3, columnspan=3, sticky="ew", pady=(8, 0))

    def _on_press(self, event):
        if not self._enabled:
            return

        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        duration = self.editor_state.playback.duration
        if duration <= 0:
            return

        hit_id, mode = self._hit_filter_block(x, y)
        if hit_id is not None:
            item = self.editor_state.get_filter(hit_id)
            if item is None:
                return
            self.editor_state.select_filter(hit_id)
            self.on_filter_select(hit_id)
            if not item.start_time <= self.editor_state.playback.current_time <= item.end_time:
                self.on_seek(item.start_time, "timeline")
            self.editor_state.record_history()

            self._drag = {
                "mode": mode,
                "filter_id": hit_id,
                "start_x": x,
                "start_y": y,
                "orig_start": item.start_time,
                "orig_end": item.end_time,
                "shift": bool(event.state & 0x0001),
            }
            self.refresh()
            return

        segment_id = self._hit_segment_block(x, y)
        if segment_id is not None:
            segment = self.editor_state.select_segment(segment_id)
            self.on_segment_select(segment_id)
            if segment is not None and not segment.contains(self.editor_state.playback.current_time, include_end=True):
                self.on_seek(segment.timeline_start, "timeline")
            self._drag = {
                "mode": "segment",
                "segment_id": segment_id,
                "start_x": x,
                "target_index": self.editor_state.segments.index(segment) if segment else 0,
                "moved": False,
            }
            self.refresh()
            return

        if y <= self.VIDEO_TOP + self.TRACK_HEIGHT:
            target = self._snap_time(self._x_to_time(x), shift=bool(event.state & 0x0001))
            self._drag = {"mode": "playhead", "shift": bool(event.state & 0x0001)}
            self.on_seek(target, "timeline")
            return

    def _on_drag(self, event):
        if not self._enabled:
            return

        if not self._drag:
            return

        x = self.canvas.canvasx(event.x)
        mode = self._drag["mode"]
        shift = bool(event.state & 0x0001) or self._drag.get("shift", False)
        if mode == "playhead":
            self.on_seek(self._snap_time(self._x_to_time(x), shift=shift), "timeline")
            return

        if mode == "segment":
            self._drag["moved"] = True
            target_index = self._segment_target_index_for_x(self._drag["segment_id"], x)
            self._drag["target_index"] = target_index
            self._snap_feedback_time = self._segment_insertion_time(self._drag["segment_id"], target_index)
            self._drag_feedback = ("Solte para inserir aqui", self._time_to_x(self._snap_feedback_time), self.VIDEO_TOP - 4)
            self.refresh(redraw_inspector=False)
            return

        filter_id = self._drag["filter_id"]
        item = self.editor_state.get_filter(filter_id)
        if item is None:
            return

        width = max(320, self.canvas.winfo_width())
        left, right = self._timeline_bounds(width)
        usable = max(1, right - left)
        delta_time = (x - self._drag["start_x"]) / usable * self.editor_state.playback.duration

        if mode == "move":
            target = self._snap_time(self._drag["orig_start"] + delta_time, ignore_id=filter_id, shift=shift)
            self.editor_state.move_filter(filter_id, target)
            self.on_seek(item.start_time, "timeline")
            feedback = f"Duração: {item.duration:.1f}s"
        elif mode == "left":
            target = self._snap_time(self._drag["orig_start"] + delta_time, ignore_id=filter_id, shift=shift)
            self.editor_state.resize_filter(filter_id, "left", target)
            self.on_seek(item.start_time, "timeline")
            feedback = f"Início: {self._format_time_precise(item.start_time)}"
        elif mode == "right":
            target = self._snap_time(self._drag["orig_end"] + delta_time, ignore_id=filter_id, shift=shift)
            self.editor_state.resize_filter(filter_id, "right", target)
            self.on_seek(item.end_time, "timeline")
            feedback = f"Fim: {self._format_time_precise(item.end_time)}"
        else:
            feedback = ""

        self.on_filter_changed(filter_id)
        if feedback:
            self._drag_feedback = (feedback, x + 8, max(18, self._drag.get("start_y", self.VIDEO_TOP)))
        self.refresh()

    def _on_release(self, _event):
        if not self._enabled:
            return
        if self._drag and self._drag.get("mode") == "segment" and self._drag.get("moved"):
            self.on_segment_move(self._drag["segment_id"], self._drag.get("target_index", 0))
        self._drag = None
        self._snap_feedback_time = None
        self._drag_feedback = None
        self.refresh(redraw_inspector=True)

    def _on_mouse_wheel(self, event):
        direction = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(direction, "units")

    def _hit_filter_block(self, x: float, y: float) -> tuple[Optional[str], str]:
        for filter_id, (left, top, right, bottom) in self._block_regions.items():
            if left <= x <= right and top <= y <= bottom:
                if x <= left + 9:
                    return filter_id, "left"
                if x >= right - 9:
                    return filter_id, "right"
                return filter_id, "move"
        return None, ""

    def _hit_segment_block(self, x: float, y: float) -> Optional[str]:
        for segment_id, (left, top, right, bottom) in self._segment_regions.items():
            if left <= x <= right and top <= y <= bottom:
                return segment_id
        return None

    def _segment_target_index_for_x(self, segment_id: str, x: float) -> int:
        target_time = self._x_to_time(x)
        others = [item for item in self.editor_state.segments if item.id != segment_id]
        for index, segment in enumerate(others):
            midpoint = (segment.timeline_start + segment.timeline_end) / 2
            if target_time < midpoint:
                return index
        return len(others)

    def _segment_insertion_time(self, segment_id: str, target_index: int) -> float:
        others = [item for item in self.editor_state.segments if item.id != segment_id]
        if not others or target_index <= 0:
            return 0.0
        if target_index >= len(others):
            return others[-1].timeline_end
        return others[target_index].timeline_start

    def _on_motion(self, event):
        if not self._enabled:
            self.canvas.configure(cursor="")
            return

        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        _filter_id, mode = self._hit_filter_block(x, y)
        if mode in ("left", "right"):
            self.canvas.configure(cursor="sb_h_double_arrow")
            return
        if mode == "move":
            self.canvas.configure(cursor="fleur")
            return
        if self._hit_segment_block(x, y) is not None:
            self.canvas.configure(cursor="fleur")
            return
        if y <= self.VIDEO_TOP + self.TRACK_HEIGHT:
            self.canvas.configure(cursor="hand2")
            return
        self.canvas.configure(cursor="")

    def _commit_entry_times(self, _event=None):
        selected = self.editor_state.selected_filter()
        if not isinstance(selected, BlurFilter):
            return

        start = self._parse_time(self.start_entry.get(), selected.start_time)
        end = self._parse_time(self.end_entry.get(), selected.end_time)
        start = max(0.0, min(start, self.editor_state.playback.duration))
        end = max(0.0, min(end, self.editor_state.playback.duration))

        if end - start < MIN_FILTER_DURATION:
            end = min(self.editor_state.playback.duration, start + MIN_FILTER_DURATION)
            if end - start < MIN_FILTER_DURATION:
                start = max(0.0, end - MIN_FILTER_DURATION)

        self.editor_state.record_history()
        selected.start_time = start
        selected.end_time = end
        self.on_filter_changed(selected.id)
        self.refresh()

    def _duplicate_selected(self):
        selected_segment = self.editor_state.selected_segment()
        if selected_segment is not None:
            self.on_segment_duplicate(selected_segment.id)
            return

        selected = self.editor_state.selected_filter()
        if selected is None:
            return
        self.on_filter_duplicate(selected.id)

    def _delete_selected(self):
        selected_segment = self.editor_state.selected_segment()
        if selected_segment is not None:
            self.on_segment_delete(selected_segment.id)
            return

        selected = self.editor_state.selected_filter()
        if selected is None:
            return
        self.on_filter_delete(selected.id)

    def _timeline_bounds(self, width: int) -> tuple[int, int]:
        return self.LABEL_WIDTH, max(self.LABEL_WIDTH + 1, width - self.RIGHT_PAD)

    def _content_height(self) -> int:
        filter_rows = max(1, len(self.editor_state.filters))
        return int(self.VIDEO_TOP + self.TRACK_HEIGHT + self.TRACK_GAP + filter_rows * (self.TRACK_HEIGHT + self.TRACK_GAP) + 34)

    def _time_to_x(self, timestamp: float, width: Optional[int] = None) -> float:
        width = max(320, width or self.canvas.winfo_width())
        left, right = self._timeline_bounds(width)
        duration = self.editor_state.playback.duration
        if duration <= 0:
            return left
        ratio = max(0.0, min(1.0, timestamp / duration))
        return left + ratio * (right - left)

    def _x_to_time(self, x: float) -> float:
        width = max(320, self.canvas.winfo_width())
        left, right = self._timeline_bounds(width)
        duration = self.editor_state.playback.duration
        if duration <= 0:
            return 0.0
        ratio = (max(left, min(right, x)) - left) / max(1, right - left)
        return ratio * duration

    def _snap_time(self, value: float, ignore_id: Optional[str] = None, shift: bool = False) -> float:
        duration = self.editor_state.playback.duration
        value = max(0.0, min(float(value), duration))
        self._snap_feedback_time = None
        if shift or duration <= 0:
            return value

        width = max(320, self.canvas.winfo_width())
        left, right = self._timeline_bounds(width)
        seconds_per_pixel = duration / max(1, right - left)
        threshold = seconds_per_pixel * 8

        candidates = [0.0, duration, self.editor_state.playback.current_time]
        candidates.extend(self._tick_times())
        for segment in self.editor_state.segments:
            candidates.extend([segment.timeline_start, segment.timeline_end])
        for item in self.editor_state.filters:
            if item.id == ignore_id:
                continue
            candidates.extend([item.start_time, item.end_time])

        nearest = min(candidates, key=lambda item: abs(item - value))
        if abs(nearest - value) <= threshold:
            self._snap_feedback_time = nearest
            return nearest
        return value

    def _tick_times(self) -> list[float]:
        duration = self.editor_state.playback.duration
        if duration <= 0:
            return [0.0]

        step = self._tick_step(duration)
        values = []
        current = 0.0
        while current < duration:
            values.append(round(current, 3))
            current += step
        if not values or values[-1] != duration:
            values.append(duration)
        return values

    def _tick_step(self, duration: float) -> float:
        if duration <= 20:
            return 5.0
        if duration <= 60:
            return 10.0
        if duration <= 180:
            return 30.0
        if duration <= 600:
            return 60.0
        if duration <= 1800:
            return 300.0
        return 600.0

    def _update_time_label(self):
        playback = self.editor_state.playback
        self.time_label.configure(
            text=f"{self._format_time_precise(playback.current_time)} / {self._format_time(playback.duration)}"
        )

    def _replace_entry_value(self, entry, value: str):
        entry.delete(0, tk.END)
        entry.insert(0, value)

    def _format_time(self, seconds: float) -> str:
        seconds = max(0, int(round(seconds or 0)))
        minutes, secs = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def _format_time_precise(self, seconds: float) -> str:
        seconds = max(0.0, float(seconds or 0.0))
        minutes = int(seconds // 60)
        secs = seconds - minutes * 60
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"
        return f"{minutes:02d}:{secs:06.3f}"

    def _format_time_span(self, start: float, end: float) -> str:
        return f"{self._format_time_precise(start)}-{self._format_time_precise(end)}"

    def _parse_time(self, text: str, fallback: float) -> float:
        value = (text or "").strip().replace(",", ".")
        if not value:
            return fallback
        try:
            parts = value.split(":")
            if len(parts) == 1:
                return float(parts[0])
            if len(parts) == 2:
                return int(parts[0]) * 60 + float(parts[1])
            if len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        except Exception:
            return fallback
        return fallback

    def _tk_font(self, size: int, weight: Optional[str] = None):
        try:
            return (self.font(size, weight).cget("family"), size, weight or "normal")
        except Exception:
            return ("Arial", size, weight or "normal")
