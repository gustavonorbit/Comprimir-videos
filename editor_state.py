"""Estado compartilhado para reproducao, segmentos e filtros temporais."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Optional
from uuid import uuid4

from blur_state import BlurState, NormalizedRect


MIN_FILTER_DURATION = 0.1
MIN_SEGMENT_DURATION = 0.1
DEFAULT_BLUR_DURATION = 5.0
DEFAULT_PRIVACY_BLUR_STRENGTH = 1.0
SELECTED_SEGMENT = "video_segment"
SELECTED_BLUR_FILTER = "blur_filter"


@dataclass
class EditorPlaybackState:
    current_time: float = 0.0
    duration: float = 0.0
    is_playing: bool = False
    selected_filter_id: Optional[str] = None
    selected_item_type: Optional[str] = None
    selected_item_id: Optional[str] = None
    seek_in_progress: bool = False
    update_source: str = "system"

    def clamp_time(self, value: float) -> float:
        if self.duration <= 0:
            return 0.0
        return max(0.0, min(float(value), self.duration))

    def set_time(self, value: float, source: str = "system") -> float:
        self.current_time = self.clamp_time(value)
        self.update_source = source
        return self.current_time

    def set_duration(self, duration: float):
        self.duration = max(0.0, float(duration or 0.0))
        self.current_time = self.clamp_time(self.current_time)


@dataclass
class BlurKeyframe:
    timestamp: float
    x: float
    y: float
    width: float
    height: float
    intensity: Optional[float] = None
    confidence: Optional[float] = None

    def serialize(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "intensity": self.intensity,
            "confidence": self.confidence,
        }


@dataclass
class BaseFilter:
    id: str
    type: str
    name: str
    start_time: float
    end_time: float
    enabled: bool = True

    @property
    def duration(self) -> float:
        return max(0.0, self.end_time - self.start_time)

    def contains(self, timestamp: float) -> bool:
        return self.enabled and self.start_time <= timestamp <= self.end_time

    def clamp_to_duration(self, duration: float):
        duration = max(0.0, float(duration or 0.0))
        self.start_time = max(0.0, min(self.start_time, duration))
        self.end_time = max(self.start_time + MIN_FILTER_DURATION, min(self.end_time, duration))
        if duration <= 0:
            self.start_time = 0.0
            self.end_time = 0.0
        elif self.end_time > duration:
            self.end_time = duration
            self.start_time = max(0.0, self.end_time - MIN_FILTER_DURATION)

    def serialize_base(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "start": self.start_time,
            "end": self.end_time,
            "enabled": self.enabled,
        }


@dataclass
class BlurFilter(BaseFilter):
    region: NormalizedRect = field(default_factory=lambda: NormalizedRect(0.25, 0.25, 0.35, 0.25))
    intensity: float = DEFAULT_PRIVACY_BLUR_STRENGTH
    clip_id: Optional[str] = None
    movement_mode: str = "fixed"
    smoothing: float = 0.0
    tracking_data: dict = field(default_factory=dict)
    keyframes: list[BlurKeyframe] = field(default_factory=list)

    def to_blur_state(self) -> BlurState:
        return BlurState(
            enabled=self.enabled,
            mode="manual",
            intensity=max(0.0, min(1.0, self.intensity)),
            region=self.region.clamped(),
        )

    def serialize(self) -> dict:
        data = self.serialize_base()
        rect = self.region.clamped()
        data.update({
            "region": {
                "x": rect.x,
                "y": rect.y,
                "width": rect.width,
                "height": rect.height,
            },
            "intensity": self.intensity,
            "clip_id": self.clip_id,
            "movement_mode": self.movement_mode,
            "smoothing": self.smoothing,
            "tracking_data": self.tracking_data,
            "keyframes": [keyframe.serialize() for keyframe in self.keyframes],
        })
        return data


@dataclass
class VideoSegment:
    id: str
    source_path: str
    source_start: float
    source_end: float
    timeline_start: float
    timeline_end: float
    enabled: bool = True
    selected: bool = False
    playback_rate: float = 1.0
    volume: float = 1.0
    transformations: dict = field(default_factory=dict)
    linked_filter_ids: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def duration(self) -> float:
        return max(0.0, self.timeline_end - self.timeline_start)

    @property
    def source_duration(self) -> float:
        return max(0.0, self.source_end - self.source_start)

    def contains(self, timestamp: float, include_end: bool = False) -> bool:
        if not self.enabled:
            return False
        if include_end:
            return self.timeline_start <= timestamp <= self.timeline_end
        return self.timeline_start <= timestamp < self.timeline_end

    def source_time_for_timeline(self, timestamp: float) -> float:
        rate = self.playback_rate if self.playback_rate > 0 else 1.0
        local_time = max(0.0, min(self.duration, float(timestamp) - self.timeline_start))
        return max(self.source_start, min(self.source_end, self.source_start + local_time * rate))

    def timeline_time_for_source(self, source_time: float) -> float:
        rate = self.playback_rate if self.playback_rate > 0 else 1.0
        local_time = max(0.0, min(self.source_duration, float(source_time) - self.source_start)) / rate
        return max(self.timeline_start, min(self.timeline_end, self.timeline_start + local_time))

    def serialize(self) -> dict:
        return {
            "id": self.id,
            "source_path": self.source_path,
            "source_start": self.source_start,
            "source_end": self.source_end,
            "timeline_start": self.timeline_start,
            "timeline_end": self.timeline_end,
            "enabled": self.enabled,
            "selected": self.selected,
            "playback_rate": self.playback_rate,
            "volume": self.volume,
            "transformations": deepcopy(self.transformations),
            "linked_filter_ids": list(self.linked_filter_ids),
            "metadata": deepcopy(self.metadata),
        }


class EditorState:
    """Modelo serializavel do workspace temporal."""

    def __init__(self):
        self.playback = EditorPlaybackState()
        self.rotation_degrees = 0
        self.segments: list[VideoSegment] = []
        self.filters: list[BaseFilter] = []
        self._blur_counter = 0
        self._segment_counter = 0
        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []
        self._history_limit = 50

    def reset(self, duration: float = 0.0, source_path: str = ""):
        self.playback = EditorPlaybackState(duration=max(0.0, float(duration or 0.0)))
        self.rotation_degrees = 0
        self.segments.clear()
        self.filters.clear()
        self._blur_counter = 0
        self._segment_counter = 0
        self._undo_stack.clear()
        self._redo_stack.clear()
        if self.playback.duration > 0 and source_path:
            self._segment_counter = 1
            segment = VideoSegment(
                id=str(uuid4()),
                source_path=source_path,
                source_start=0.0,
                source_end=self.playback.duration,
                timeline_start=0.0,
                timeline_end=self.playback.duration,
                selected=True,
                metadata={"index": self._segment_counter},
            )
            self.segments.append(segment)
            self.playback.selected_item_type = SELECTED_SEGMENT
            self.playback.selected_item_id = segment.id

    def set_duration(self, duration: float):
        self.playback.set_duration(duration)
        for segment in self.segments:
            segment.timeline_start = max(0.0, min(segment.timeline_start, self.playback.duration))
            segment.timeline_end = max(segment.timeline_start, min(segment.timeline_end, self.playback.duration))
        for item in self.filters:
            item.clamp_to_duration(self.playback.duration)

    def add_media_segment(
        self,
        source_path: str,
        duration: float,
        insert_index: Optional[int] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[VideoSegment]:
        duration = max(0.0, float(duration or 0.0))
        if not source_path or duration <= 0:
            return None

        self._push_history()
        self._segment_counter += 1
        segment = VideoSegment(
            id=str(uuid4()),
            source_path=source_path,
            source_start=0.0,
            source_end=duration,
            timeline_start=0.0,
            timeline_end=duration,
            selected=True,
            metadata={"index": self._segment_counter, **(metadata or {})},
        )

        if insert_index is None:
            insert_index = len(self.segments)
        insert_index = max(0, min(int(insert_index), len(self.segments)))
        self.segments.insert(insert_index, segment)
        self._pack_segments_preserving_order()
        self.select_segment(segment.id)
        self.playback.set_time(segment.timeline_start, "timeline")
        return segment

    def insertion_index_for_time(self, timestamp: float) -> int:
        if not self.segments:
            return 0

        timestamp = self.playback.clamp_time(timestamp)
        for index, segment in enumerate(self.segments):
            midpoint = (segment.timeline_start + segment.timeline_end) / 2
            if timestamp < midpoint:
                return index
        return len(self.segments)

    def add_blur(
        self,
        start_time: float,
        region: NormalizedRect,
        intensity: float = DEFAULT_PRIVACY_BLUR_STRENGTH,
        default_duration: float = DEFAULT_BLUR_DURATION,
    ) -> BlurFilter:
        self._push_history()
        duration = self.playback.duration
        start = self.playback.clamp_time(start_time)
        segment = self.segment_at_time(start)
        if duration <= 0:
            end = start
        elif segment is not None:
            end = segment.timeline_end
            if end - start < MIN_FILTER_DURATION:
                start = max(segment.timeline_start, end - MIN_FILTER_DURATION)
        else:
            end = min(duration, start + max(MIN_FILTER_DURATION, default_duration))
            if end - start < MIN_FILTER_DURATION:
                start = max(0.0, end - MIN_FILTER_DURATION)

        self._blur_counter += 1
        blur = BlurFilter(
            id=str(uuid4()),
            type="blur",
            name=f"Blur {self._blur_counter}",
            start_time=start,
            end_time=end,
            enabled=True,
            region=region.clamped(),
            intensity=max(0.0, min(1.0, intensity)),
            clip_id=segment.id if segment is not None else None,
        )
        self.filters.append(blur)
        self._rebuild_filter_links()
        self.select_filter(blur.id)
        return blur

    def duplicate_filter(self, filter_id: str) -> Optional[BaseFilter]:
        item = self.get_filter(filter_id)
        if not isinstance(item, BlurFilter):
            return None

        self._push_history()
        self._blur_counter += 1
        offset = min(1.0, max(0.0, self.playback.duration - item.end_time))
        duplicate = BlurFilter(
            id=str(uuid4()),
            type=item.type,
            name=f"Blur {self._blur_counter}",
            start_time=item.start_time + offset,
            end_time=item.end_time + offset,
            enabled=item.enabled,
            region=item.region.clamped(),
            intensity=item.intensity,
            clip_id=item.clip_id,
            movement_mode=item.movement_mode,
            smoothing=item.smoothing,
            tracking_data=dict(item.tracking_data),
            keyframes=list(item.keyframes),
        )
        duplicate.clamp_to_duration(self.playback.duration)
        self.filters.append(duplicate)
        self._rebuild_filter_links()
        self.select_filter(duplicate.id)
        return duplicate

    def delete_filter(self, filter_id: str):
        if self.get_filter(filter_id) is None:
            return

        self._push_history()
        self.filters = [item for item in self.filters if item.id != filter_id]
        self._rebuild_filter_links()
        if self.playback.selected_filter_id == filter_id:
            self.playback.selected_filter_id = None
            if self.playback.selected_item_id == filter_id:
                self.playback.selected_item_type = None
                self.playback.selected_item_id = None

    def select_filter(self, filter_id: Optional[str]):
        if filter_id is None or self.get_filter(filter_id) is None:
            self.playback.selected_filter_id = None
            if self.playback.selected_item_type == SELECTED_BLUR_FILTER:
                self.playback.selected_item_type = None
                self.playback.selected_item_id = None
            return
        self.playback.selected_filter_id = filter_id
        self.playback.selected_item_type = SELECTED_BLUR_FILTER
        self.playback.selected_item_id = filter_id
        for segment in self.segments:
            segment.selected = False

    def get_filter(self, filter_id: Optional[str]) -> Optional[BaseFilter]:
        if filter_id is None:
            return None
        for item in self.filters:
            if item.id == filter_id:
                return item
        return None

    def selected_filter(self) -> Optional[BaseFilter]:
        return self.get_filter(self.playback.selected_filter_id)

    def select_segment(self, segment_id: Optional[str]) -> Optional[VideoSegment]:
        selected = self.get_segment(segment_id)
        for segment in self.segments:
            segment.selected = selected is not None and segment.id == selected.id

        if selected is None:
            if self.playback.selected_item_type == SELECTED_SEGMENT:
                self.playback.selected_item_type = None
                self.playback.selected_item_id = None
            return None

        self.playback.selected_filter_id = None
        self.playback.selected_item_type = SELECTED_SEGMENT
        self.playback.selected_item_id = selected.id
        return selected

    def get_segment(self, segment_id: Optional[str]) -> Optional[VideoSegment]:
        if segment_id is None:
            return None
        for segment in self.segments:
            if segment.id == segment_id:
                return segment
        return None

    def selected_segment(self) -> Optional[VideoSegment]:
        if self.playback.selected_item_type != SELECTED_SEGMENT:
            return None
        return self.get_segment(self.playback.selected_item_id)

    def segment_at_time(self, timestamp: float) -> Optional[VideoSegment]:
        if not self.segments:
            return None

        timestamp = self.playback.clamp_time(timestamp)
        last = self.segments[-1]
        if abs(timestamp - last.timeline_end) <= 1e-6:
            return last

        for segment in self.segments:
            if segment.contains(timestamp):
                return segment
        return None

    def timeline_time_to_source(self, timestamp: float) -> Optional[tuple[VideoSegment, float]]:
        segment = self.segment_at_time(timestamp)
        if segment is None:
            return None
        return segment, segment.source_time_for_timeline(timestamp)

    def source_time_to_timeline(self, source_path: str, source_time: float) -> Optional[float]:
        for segment in self.segments:
            if segment.source_path != source_path:
                continue
            if segment.source_start <= source_time <= segment.source_end:
                return segment.timeline_time_for_source(source_time)
        return None

    def can_split_at(self, timestamp: float) -> bool:
        return self.split_validation_error(timestamp) is None

    def split_validation_error(self, timestamp: float) -> Optional[str]:
        segment = self.segment_at_time(timestamp)
        if segment is None:
            return "Não há segmento no tempo atual."

        timestamp = self.playback.clamp_time(timestamp)
        left_duration = timestamp - segment.timeline_start
        right_duration = segment.timeline_end - timestamp
        if left_duration < MIN_SEGMENT_DURATION or right_duration < MIN_SEGMENT_DURATION:
            return "Posicione o playhead mais longe do início ou fim do segmento."
        return None

    def split_segment_at(self, timestamp: float) -> tuple[Optional[VideoSegment], str]:
        error = self.split_validation_error(timestamp)
        if error is not None:
            return None, error

        segment = self.segment_at_time(timestamp)
        if segment is None:
            return None, "Não há segmento no tempo atual."

        self._push_history()
        timestamp = self.playback.clamp_time(timestamp)
        source_cut = segment.source_time_for_timeline(timestamp)
        index = self.segments.index(segment)
        old_timeline_end = segment.timeline_end
        old_source_end = segment.source_end

        segment.timeline_end = timestamp
        segment.source_end = source_cut
        segment.selected = False

        self._segment_counter += 1
        right = VideoSegment(
            id=str(uuid4()),
            source_path=segment.source_path,
            source_start=source_cut,
            source_end=old_source_end,
            timeline_start=timestamp,
            timeline_end=old_timeline_end,
            enabled=segment.enabled,
            selected=True,
            playback_rate=segment.playback_rate,
            volume=segment.volume,
            transformations=deepcopy(segment.transformations),
            linked_filter_ids=list(segment.linked_filter_ids),
            metadata={**deepcopy(segment.metadata), "index": self._segment_counter},
        )
        self.segments.insert(index + 1, right)
        self._split_filters_for_segment(segment.id, right.id, timestamp)
        self._rebuild_filter_links()
        self.select_segment(right.id)
        self.playback.set_time(timestamp, "timeline")
        return right, "Clipe dividido."

    def delete_selected_segment_ripple(self) -> tuple[bool, str]:
        segment = self.selected_segment()
        if segment is None:
            return False, "Nenhum segmento selecionado."
        return self.delete_segment_ripple(segment.id)

    def delete_segment_ripple(self, segment_id: str) -> tuple[bool, str]:
        segment = self.get_segment(segment_id)
        if segment is None:
            return False, "Segmento não encontrado."
        if len(self.segments) <= 1:
            return False, "Mantenha pelo menos um segmento na timeline."

        self._push_history()
        index = self.segments.index(segment)
        delete_start = segment.timeline_start
        delete_end = segment.timeline_end
        delta = max(0.0, delete_end - delete_start)

        self.segments.pop(index)
        for later in self.segments[index:]:
            later.timeline_start = max(0.0, later.timeline_start - delta)
            later.timeline_end = max(later.timeline_start, later.timeline_end - delta)

        self._adjust_filters_for_ripple_delete(delete_start, delete_end)
        self.playback.set_duration(max(0.0, self.playback.duration - delta))

        if delete_start <= self.playback.current_time <= delete_end:
            self.playback.set_time(delete_start, "timeline")
        elif self.playback.current_time > delete_end:
            self.playback.set_time(self.playback.current_time - delta, "timeline")
        else:
            self.playback.set_time(self.playback.current_time, "timeline")

        if self.segments:
            next_index = min(index, len(self.segments) - 1)
            self.select_segment(self.segments[next_index].id)
        else:
            self.playback.selected_item_type = None
            self.playback.selected_item_id = None
            self.playback.selected_filter_id = None
        self._rebuild_filter_links()
        return True, "Segmento excluído e espaço fechado."

    def duplicate_segment(self, segment_id: str) -> Optional[VideoSegment]:
        segment = self.get_segment(segment_id)
        if segment is None:
            return None

        self._push_history()
        index = self.segments.index(segment)
        delta = segment.duration
        insert_time = segment.timeline_end

        for later in self.segments[index + 1:]:
            later.timeline_start += delta
            later.timeline_end += delta

        self._shift_filters_for_insert(insert_time, delta)
        self.playback.set_duration(self.playback.duration + delta)

        self._segment_counter += 1
        duplicate = VideoSegment(
            id=str(uuid4()),
            source_path=segment.source_path,
            source_start=segment.source_start,
            source_end=segment.source_end,
            timeline_start=insert_time,
            timeline_end=insert_time + delta,
            enabled=segment.enabled,
            selected=True,
            playback_rate=segment.playback_rate,
            volume=segment.volume,
            transformations=deepcopy(segment.transformations),
            linked_filter_ids=[],
            metadata={**deepcopy(segment.metadata), "index": self._segment_counter},
        )
        self.segments.insert(index + 1, duplicate)
        self._duplicate_linked_filters(segment, duplicate)
        self._rebuild_filter_links()
        self.select_segment(duplicate.id)
        self.playback.set_time(duplicate.timeline_start, "timeline")
        return duplicate

    def move_segment_to_index(self, segment_id: str, target_index: int) -> Optional[VideoSegment]:
        segment = self.get_segment(segment_id)
        if segment is None:
            return None

        self._push_history()
        original_order = list(self.segments)
        old_positions = {item.id: item.timeline_start for item in original_order}
        self.segments.remove(segment)
        target_index = max(0, min(int(target_index), len(self.segments)))
        self.segments.insert(target_index, segment)
        self._pack_segments_preserving_order()
        self._rebuild_filter_links()
        self.select_segment(segment.id)
        self.playback.set_time(segment.timeline_start, "timeline")
        return segment

    def move_segment_to_time(self, segment_id: str, timestamp: float) -> Optional[VideoSegment]:
        segment = self.get_segment(segment_id)
        if segment is None:
            return None

        others = [item for item in self.segments if item.id != segment_id]
        target = self.playback.clamp_time(timestamp)
        target_index = len(others)
        for index, item in enumerate(others):
            midpoint = (item.timeline_start + item.timeline_end) / 2
            if target < midpoint:
                target_index = index
                break
        return self.move_segment_to_index(segment_id, target_index)

    def move_filter(self, filter_id: str, new_start: float):
        item = self.get_filter(filter_id)
        if item is None:
            return

        length = max(MIN_FILTER_DURATION, item.duration)
        start_bound, end_bound = self._filter_bounds(item)
        start = max(start_bound, min(float(new_start), max(start_bound, end_bound - length)))
        item.start_time = start
        item.end_time = min(end_bound, start + length)

    def resize_filter(self, filter_id: str, edge: str, new_time: float):
        item = self.get_filter(filter_id)
        if item is None:
            return

        start_bound, end_bound = self._filter_bounds(item)
        value = max(start_bound, min(float(new_time), end_bound))
        if edge == "left":
            item.start_time = min(value, item.end_time - MIN_FILTER_DURATION)
            item.start_time = max(start_bound, item.start_time)
        elif edge == "right":
            item.end_time = max(value, item.start_time + MIN_FILTER_DURATION)
            item.end_time = min(end_bound, item.end_time)

    def update_filter_region(self, filter_id: str, region: NormalizedRect):
        item = self.get_filter(filter_id)
        if isinstance(item, BlurFilter):
            item.region = region.clamped()

    def set_rotation(self, rotation: int):
        self.rotation_degrees = rotation if rotation in (0, 90, 180, 270) else 0

    def rotate_workspace(self, new_rotation: int):
        new_rotation = new_rotation if new_rotation in (0, 90, 180, 270) else 0
        old_rotation = self.rotation_degrees
        if old_rotation == new_rotation:
            return

        self._push_history()
        delta = (new_rotation - old_rotation) % 360
        self.transform_blur_regions_for_rotation(delta, record_history=False)
        self.rotation_degrees = new_rotation

    def transform_blur_regions_for_rotation(self, rotation_delta: int, record_history: bool = True):
        rotation_delta = rotation_delta % 360
        if rotation_delta not in (90, 180, 270):
            return

        if record_history:
            self._push_history()
        for item in self.filters:
            if isinstance(item, BlurFilter):
                item.region = self._rotate_region(item.region, rotation_delta)

    def _filter_bounds(self, item: BaseFilter) -> tuple[float, float]:
        if isinstance(item, BlurFilter) and item.clip_id:
            segment = self.get_segment(item.clip_id)
            if segment is not None:
                return segment.timeline_start, segment.timeline_end
        return 0.0, self.playback.duration

    def _pack_segments_preserving_order(self):
        current = 0.0
        old_positions = {segment.id: segment.timeline_start for segment in self.segments}
        for segment in self.segments:
            length = max(MIN_SEGMENT_DURATION, segment.duration or segment.source_duration)
            segment.timeline_start = current
            segment.timeline_end = current + length
            current = segment.timeline_end
        self.playback.set_duration(current)
        self._move_linked_filters_after_segment_reorder(old_positions)

    def _move_linked_filters_after_segment_reorder(self, old_positions: dict[str, float]):
        for item in self.filters:
            if not isinstance(item, BlurFilter) or not item.clip_id:
                continue
            segment = self.get_segment(item.clip_id)
            if segment is None:
                continue
            old_start = old_positions.get(segment.id, segment.timeline_start)
            delta = segment.timeline_start - old_start
            item.start_time += delta
            item.end_time += delta
            self._clamp_filter_to_segment(item, segment)

    def _clamp_filter_to_segment(self, item: BlurFilter, segment: VideoSegment):
        item.start_time = max(segment.timeline_start, min(item.start_time, segment.timeline_end))
        item.end_time = max(item.start_time + MIN_FILTER_DURATION, min(item.end_time, segment.timeline_end))
        if item.end_time > segment.timeline_end:
            item.end_time = segment.timeline_end
            item.start_time = max(segment.timeline_start, item.end_time - MIN_FILTER_DURATION)

    def _split_filters_for_segment(self, left_id: str, right_id: str, cut_time: float):
        new_filters: list[BaseFilter] = []
        for item in list(self.filters):
            if not isinstance(item, BlurFilter):
                continue

            belongs_to_left = item.clip_id == left_id
            if not belongs_to_left and item.clip_id is None:
                segment = self.get_segment(left_id)
                belongs_to_left = segment is not None and segment.timeline_start <= item.start_time < segment.timeline_end
            if not belongs_to_left:
                continue

            if item.end_time <= cut_time:
                item.clip_id = left_id
            elif item.start_time >= cut_time:
                item.clip_id = right_id
            else:
                original_end = item.end_time
                item.end_time = cut_time
                item.clip_id = left_id
                self._blur_counter += 1
                duplicate = BlurFilter(
                    id=str(uuid4()),
                    type=item.type,
                    name=f"Blur {self._blur_counter}",
                    start_time=cut_time,
                    end_time=original_end,
                    enabled=item.enabled,
                    region=item.region.clamped(),
                    intensity=item.intensity,
                    clip_id=right_id,
                    movement_mode=item.movement_mode,
                    smoothing=item.smoothing,
                    tracking_data=deepcopy(item.tracking_data),
                    keyframes=[
                        keyframe for keyframe in item.keyframes
                        if cut_time <= keyframe.timestamp <= original_end
                    ],
                )
                new_filters.append(duplicate)

        self.filters.extend(new_filters)

    def _duplicate_linked_filters(self, source: VideoSegment, duplicate: VideoSegment):
        copied: list[BaseFilter] = []
        for item in self.filters:
            if not isinstance(item, BlurFilter) or item.clip_id != source.id:
                continue
            relative_start = max(0.0, item.start_time - source.timeline_start)
            relative_end = max(relative_start + MIN_FILTER_DURATION, item.end_time - source.timeline_start)
            self._blur_counter += 1
            copied.append(BlurFilter(
                id=str(uuid4()),
                type=item.type,
                name=f"Blur {self._blur_counter}",
                start_time=duplicate.timeline_start + relative_start,
                end_time=min(duplicate.timeline_end, duplicate.timeline_start + relative_end),
                enabled=item.enabled,
                region=item.region.clamped(),
                intensity=item.intensity,
                clip_id=duplicate.id,
                movement_mode=item.movement_mode,
                smoothing=item.smoothing,
                tracking_data=deepcopy(item.tracking_data),
                keyframes=[
                    BlurKeyframe(
                        timestamp=duplicate.timeline_start + max(0.0, keyframe.timestamp - source.timeline_start),
                        x=keyframe.x,
                        y=keyframe.y,
                        width=keyframe.width,
                        height=keyframe.height,
                        intensity=keyframe.intensity,
                        confidence=keyframe.confidence,
                    )
                    for keyframe in item.keyframes
                ],
            ))
        self.filters.extend(copied)

    def _rebuild_filter_links(self):
        for segment in self.segments:
            segment.linked_filter_ids = []

        for item in self.filters:
            if not isinstance(item, BlurFilter):
                continue
            segment = self.get_segment(item.clip_id)
            if segment is None:
                segment = self.segment_at_time(item.start_time)
                item.clip_id = segment.id if segment is not None else None
            if segment is not None and item.id not in segment.linked_filter_ids:
                segment.linked_filter_ids.append(item.id)

    def _rotate_region(self, region: NormalizedRect, rotation_delta: int) -> NormalizedRect:
        rect = region.clamped()
        points = (
            (rect.x, rect.y),
            (rect.x + rect.width, rect.y),
            (rect.x, rect.y + rect.height),
            (rect.x + rect.width, rect.y + rect.height),
        )

        rotated = [self._rotate_point(x, y, rotation_delta) for x, y in points]
        xs = [point[0] for point in rotated]
        ys = [point[1] for point in rotated]
        return NormalizedRect(
            min(xs),
            min(ys),
            max(xs) - min(xs),
            max(ys) - min(ys),
        ).clamped()

    def _rotate_point(self, x: float, y: float, rotation_delta: int) -> tuple[float, float]:
        if rotation_delta == 90:
            return 1.0 - y, x
        if rotation_delta == 180:
            return 1.0 - x, 1.0 - y
        return y, 1.0 - x

    def active_blur_states(self, timestamp: Optional[float] = None) -> list[BlurState]:
        if timestamp is None:
            timestamp = self.playback.current_time
        states: list[BlurState] = []
        for item in self.filters:
            if isinstance(item, BlurFilter) and item.contains(timestamp):
                states.append(item.to_blur_state())
        return states

    def blur_filters_for_export(self) -> list[BlurFilter]:
        return [
            item for item in self.filters
            if isinstance(item, BlurFilter)
            and item.enabled
            and item.region.is_usable()
            and item.intensity > 0
            and item.end_time > item.start_time
        ]

    def segments_for_export(self) -> list[VideoSegment]:
        return [
            segment for segment in self.segments
            if segment.enabled and segment.timeline_end > segment.timeline_start and segment.source_end > segment.source_start
        ]

    def undo(self) -> bool:
        if not self._undo_stack:
            return False
        current = self._snapshot()
        snapshot = self._undo_stack.pop()
        self._redo_stack.append(current)
        self._restore_snapshot(snapshot)
        return True

    def redo(self) -> bool:
        if not self._redo_stack:
            return False
        current = self._snapshot()
        snapshot = self._redo_stack.pop()
        self._undo_stack.append(current)
        self._restore_snapshot(snapshot)
        return True

    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def record_history(self):
        self._push_history()

    def clear_history(self):
        self._undo_stack.clear()
        self._redo_stack.clear()

    def serialize(self) -> dict:
        return {
            "duration": self.playback.duration,
            "current_time": self.playback.current_time,
            "rotation_degrees": self.rotation_degrees,
            "selected_filter_id": self.playback.selected_filter_id,
            "selected_item_type": self.playback.selected_item_type,
            "selected_item_id": self.playback.selected_item_id,
            "segments": [segment.serialize() for segment in self.segments],
            "filters": [
                item.serialize() if hasattr(item, "serialize") else item.serialize_base()
                for item in self.filters
            ],
        }

    def _adjust_filters_for_ripple_delete(self, delete_start: float, delete_end: float):
        delta = max(0.0, delete_end - delete_start)
        adjusted: list[BaseFilter] = []

        for item in self.filters:
            start = item.start_time
            end = item.end_time

            if end <= delete_start:
                adjusted.append(item)
                continue

            if start >= delete_end:
                item.start_time = max(0.0, start - delta)
                item.end_time = max(item.start_time, end - delta)
                self._adjust_filter_keyframes_for_ripple(item, delete_start, delete_end, delta)
                adjusted.append(item)
                continue

            if start < delete_start and end > delete_end:
                item.end_time = end - delta
            elif start < delete_start < end <= delete_end:
                item.end_time = delete_start
            elif delete_start <= start < delete_end < end:
                item.start_time = delete_start
                item.end_time = end - delta
            else:
                continue

            self._adjust_filter_keyframes_for_ripple(item, delete_start, delete_end, delta)
            if item.end_time - item.start_time >= MIN_FILTER_DURATION:
                adjusted.append(item)

        self.filters = adjusted
        if self.playback.selected_filter_id and self.get_filter(self.playback.selected_filter_id) is None:
            self.select_filter(None)

    def _shift_filters_for_insert(self, insert_time: float, delta: float):
        if delta <= 0:
            return

        for item in self.filters:
            if item.start_time >= insert_time:
                item.start_time += delta
                item.end_time += delta
            elif item.start_time < insert_time < item.end_time:
                item.end_time += delta
            if isinstance(item, BlurFilter) and item.keyframes:
                shifted = []
                for keyframe in item.keyframes:
                    if keyframe.timestamp >= insert_time:
                        shifted.append(BlurKeyframe(
                            timestamp=keyframe.timestamp + delta,
                            x=keyframe.x,
                            y=keyframe.y,
                            width=keyframe.width,
                            height=keyframe.height,
                            intensity=keyframe.intensity,
                            confidence=keyframe.confidence,
                        ))
                    else:
                        shifted.append(keyframe)
                item.keyframes = shifted

    def _adjust_filter_keyframes_for_ripple(
        self,
        item: BaseFilter,
        delete_start: float,
        delete_end: float,
        delta: float
    ):
        if not isinstance(item, BlurFilter) or not item.keyframes:
            return

        keyframes: list[BlurKeyframe] = []
        for keyframe in item.keyframes:
            if keyframe.timestamp < delete_start:
                keyframes.append(keyframe)
            elif keyframe.timestamp >= delete_end:
                keyframes.append(BlurKeyframe(
                    timestamp=max(0.0, keyframe.timestamp - delta),
                    x=keyframe.x,
                    y=keyframe.y,
                    width=keyframe.width,
                    height=keyframe.height,
                    intensity=keyframe.intensity,
                    confidence=keyframe.confidence,
                ))
        item.keyframes = keyframes

    def _push_history(self):
        snapshot = self._snapshot()
        self._undo_stack.append(snapshot)
        if len(self._undo_stack) > self._history_limit:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def _snapshot(self) -> dict:
        data = self.serialize()
        data.update({
            "blur_counter": self._blur_counter,
            "segment_counter": self._segment_counter,
        })
        return deepcopy(data)

    def _restore_snapshot(self, snapshot: dict):
        self.playback = EditorPlaybackState(
            current_time=float(snapshot.get("current_time", 0.0) or 0.0),
            duration=float(snapshot.get("duration", 0.0) or 0.0),
            selected_filter_id=snapshot.get("selected_filter_id"),
            selected_item_type=snapshot.get("selected_item_type"),
            selected_item_id=snapshot.get("selected_item_id"),
        )
        self._blur_counter = int(snapshot.get("blur_counter", 0) or 0)
        self._segment_counter = int(snapshot.get("segment_counter", 0) or 0)
        self.rotation_degrees = int(snapshot.get("rotation_degrees", 0) or 0)
        if self.rotation_degrees not in (0, 90, 180, 270):
            self.rotation_degrees = 0
        self.segments = [self._segment_from_dict(item) for item in snapshot.get("segments", [])]
        self.filters = [self._filter_from_dict(item) for item in snapshot.get("filters", [])]
        self._rebuild_filter_links()

        selected_segment = self.get_segment(self.playback.selected_item_id)
        for segment in self.segments:
            segment.selected = selected_segment is not None and segment.id == selected_segment.id

        if self.playback.selected_item_type == SELECTED_BLUR_FILTER:
            if self.get_filter(self.playback.selected_item_id) is None:
                self.playback.selected_item_type = None
                self.playback.selected_item_id = None
                self.playback.selected_filter_id = None
            else:
                self.playback.selected_filter_id = self.playback.selected_item_id
        elif self.playback.selected_item_type == SELECTED_SEGMENT:
            self.playback.selected_filter_id = None
            if selected_segment is None:
                self.playback.selected_item_type = None
                self.playback.selected_item_id = None
        self.playback.set_time(self.playback.current_time, "history")

    def _segment_from_dict(self, data: dict) -> VideoSegment:
        return VideoSegment(
            id=data.get("id") or str(uuid4()),
            source_path=data.get("source_path", ""),
            source_start=float(data.get("source_start", 0.0) or 0.0),
            source_end=float(data.get("source_end", 0.0) or 0.0),
            timeline_start=float(data.get("timeline_start", 0.0) or 0.0),
            timeline_end=float(data.get("timeline_end", 0.0) or 0.0),
            enabled=bool(data.get("enabled", True)),
            selected=bool(data.get("selected", False)),
            playback_rate=float(data.get("playback_rate", 1.0) or 1.0),
            volume=float(data.get("volume", 1.0) or 1.0),
            transformations=deepcopy(data.get("transformations", {})),
            linked_filter_ids=list(data.get("linked_filter_ids", [])),
            metadata=deepcopy(data.get("metadata", {})),
        )

    def _filter_from_dict(self, data: dict) -> BaseFilter:
        if data.get("type") == "blur":
            region_data = data.get("region", {})
            def region_value(key: str, default: float) -> float:
                value = region_data.get(key, default)
                return default if value is None else float(value)

            return BlurFilter(
                id=data.get("id") or str(uuid4()),
                type="blur",
                name=data.get("name", "Blur"),
                start_time=float(data.get("start", 0.0) or 0.0),
                end_time=float(data.get("end", 0.0) or 0.0),
                enabled=bool(data.get("enabled", True)),
                region=NormalizedRect(
                    region_value("x", 0.25),
                    region_value("y", 0.25),
                    region_value("width", 0.35),
                    region_value("height", 0.25),
                ).clamped(),
                intensity=float(data.get("intensity", DEFAULT_PRIVACY_BLUR_STRENGTH) or DEFAULT_PRIVACY_BLUR_STRENGTH),
                clip_id=data.get("clip_id"),
                movement_mode=data.get("movement_mode", "fixed"),
                smoothing=float(data.get("smoothing", 0.0) or 0.0),
                tracking_data=deepcopy(data.get("tracking_data", {})),
                keyframes=[
                    BlurKeyframe(
                        timestamp=float(keyframe.get("timestamp", 0.0) or 0.0),
                        x=float(keyframe.get("x", 0.0) or 0.0),
                        y=float(keyframe.get("y", 0.0) or 0.0),
                        width=float(keyframe.get("width", 0.0) or 0.0),
                        height=float(keyframe.get("height", 0.0) or 0.0),
                        intensity=keyframe.get("intensity"),
                        confidence=keyframe.get("confidence"),
                    )
                    for keyframe in data.get("keyframes", [])
                ],
            )

        return BaseFilter(
            id=data.get("id") or str(uuid4()),
            type=data.get("type", "filter"),
            name=data.get("name", "Filtro"),
            start_time=float(data.get("start", 0.0) or 0.0),
            end_time=float(data.get("end", 0.0) or 0.0),
            enabled=bool(data.get("enabled", True)),
        )
