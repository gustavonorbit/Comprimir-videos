"""Geracao de filtros de video usados pela previa e pela compressao."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from blur_state import BlurState, NormalizedRect


VALID_ROTATIONS = (0, 90, 180, 270)


@dataclass(frozen=True)
class BlurFilterParams:
    luma_radius: int
    luma_power: int
    chroma_radius: int
    chroma_power: int


def rotation_filter(rotation: int) -> str:
    rotation_filters = {
        90: "transpose=1",
        180: "hflip,vflip",
        270: "transpose=2",
    }
    return rotation_filters.get(rotation, "")


def rotated_dimensions(width: int, height: int, rotation: int) -> tuple[int, int]:
    if rotation in (90, 270):
        return height, width
    return width, height


def region_to_pixels(region: NormalizedRect, width: int, height: int) -> tuple[int, int, int, int]:
    rect = region.clamped()
    x = int(round(rect.x * width))
    y = int(round(rect.y * height))
    rect_width = int(round(rect.width * width))
    rect_height = int(round(rect.height * height))

    x = max(0, min(max(0, width - 2), x))
    y = max(0, min(max(0, height - 2), y))
    rect_width = max(2, min(width - x, rect_width))
    rect_height = max(2, min(height - y, rect_height))
    return x, y, rect_width, rect_height


def map_blur_intensity(
    intensity: float,
    region_width: Optional[int] = None,
    region_height: Optional[int] = None
) -> BlurFilterParams:
    """Converte a intensidade normalizada nos parametros reais do FFmpeg."""
    intensity = max(0.0, min(1.0, float(intensity)))
    if intensity <= 0:
        return BlurFilterParams(0, 0, 0, 0)

    curved = intensity ** 2
    radius = max(1, int(round(2 + curved * 46)))

    if region_width is not None and region_height is not None:
        smaller_side = max(2, min(int(region_width), int(region_height)))
        luma_limit = max(1, (smaller_side - 1) // 2)
        chroma_limit = min(15, max(1, (smaller_side - 1) // 4))
        radius = min(radius, luma_limit)
    else:
        chroma_limit = 15

    if intensity >= 0.75:
        power = 3
    elif intensity >= 0.45:
        power = 2
    else:
        power = 1

    return BlurFilterParams(
        luma_radius=radius,
        luma_power=power,
        chroma_radius=min(radius, chroma_limit),
        chroma_power=min(power, 2),
    )


def blur_radius(intensity: float) -> int:
    return map_blur_intensity(intensity).luma_radius


def _plain_filter(tail_filters: Sequence[str], linear_filters: Sequence[str]) -> str:
    filters = [item for item in linear_filters if item]
    filters.extend(item for item in tail_filters if item)
    return ",".join(filters)


def _active_blur_states(blur_states: Optional[Sequence[BlurState]]) -> list[BlurState]:
    states: list[BlurState] = []
    if blur_states:
        states.extend(state.copy() for state in blur_states if state and state.has_effect())
    return states


def _temporal_blur_items(temporal_blurs: Optional[Sequence]) -> list[tuple[float, float, BlurState]]:
    items: list[tuple[float, float, BlurState]] = []
    for item in temporal_blurs or []:
        try:
            start_time = float(getattr(item, "start_time"))
            end_time = float(getattr(item, "end_time"))
            state = item.to_blur_state()
        except Exception:
            continue

        if end_time <= start_time or not state.has_effect():
            continue
        items.append((max(0.0, start_time), max(0.0, end_time), state))
    return items


def _build_blur_pipeline(
    source_width: int,
    source_height: int,
    rotation: int,
    blur_items: Sequence[tuple[Optional[float], Optional[float], BlurState]],
    tail_filters: Sequence[str],
    label_prefix: str = "",
) -> str:
    rotate = rotation_filter(rotation)
    linear_filters = [rotate] if rotate else []
    rotated_width, rotated_height = rotated_dimensions(source_width, source_height, rotation)
    graph_parts = []
    current_label: Optional[str] = None
    valid_items = []

    for start_time, end_time, state in blur_items:
        if not state.has_effect():
            continue
        x, y, width, height = region_to_pixels(state.region, rotated_width, rotated_height)
        blur_params = map_blur_intensity(state.intensity, width, height)
        if blur_params.luma_radius <= 0:
            continue
        valid_items.append((start_time, end_time, x, y, width, height, blur_params))

    if not valid_items:
        return _plain_filter(tail_filters, linear_filters)

    for index, item in enumerate(valid_items):
        start_time, end_time, x, y, width, height, blur_params = item
        is_last = index == len(valid_items) - 1
        needs_output_label = bool(tail_filters) or not is_last
        base_label = f"{label_prefix}base{index}"
        blur_label = f"{label_prefix}blur{index}"
        blurred_label = f"{label_prefix}blurred{index}"
        output_label = f"{label_prefix}vblur{index}"

        if current_label is None:
            prefix = ",".join(linear_filters)
            split_source = f"{prefix}," if prefix else ""
        else:
            split_source = f"[{current_label}]"

        split_part = f"{split_source}split[{base_label}][{blur_label}]"
        crop_part = (
            f"[{blur_label}]crop={width}:{height}:{x}:{y},"
            f"boxblur=luma_radius={blur_params.luma_radius}:"
            f"luma_power={blur_params.luma_power}:"
            f"chroma_radius={blur_params.chroma_radius}:"
            f"chroma_power={blur_params.chroma_power}[{blurred_label}]"
        )
        overlay_part = f"[{base_label}][{blurred_label}]overlay={x}:{y}"
        if start_time is not None and end_time is not None:
            overlay_part = f"{overlay_part}:enable='between(t,{start_time:.3f},{end_time:.3f})'"
        if needs_output_label:
            overlay_part = f"{overlay_part}[{output_label}]"
            current_label = output_label
        else:
            current_label = None

        graph_parts.extend([split_part, crop_part, overlay_part])

    if tail_filters:
        tail = ",".join(tail_filters)
        graph_parts.append(f"[{current_label}]{tail}")

    return ";".join(graph_parts)


def build_video_filter(
    source_width: int,
    source_height: int,
    rotation: int = 0,
    blur_states: Optional[Sequence[BlurState]] = None,
    temporal_blurs: Optional[Sequence] = None,
    tail_filters: Optional[Sequence[str]] = None,
    label_prefix: str = "",
) -> str:
    tail_filters = [item for item in (tail_filters or []) if item]
    if temporal_blurs:
        temporal_items = _temporal_blur_items(temporal_blurs)
        return _build_blur_pipeline(source_width, source_height, rotation, temporal_items, tail_filters, label_prefix)

    states = _active_blur_states(blur_states)
    blur_items = [(None, None, state) for state in states]
    return _build_blur_pipeline(source_width, source_height, rotation, blur_items, tail_filters, label_prefix)
