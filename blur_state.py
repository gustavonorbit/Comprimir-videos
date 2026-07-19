"""Estado compartilhado para blur manual."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class NormalizedRect:
    """Retangulo normalizado no video ja orientado/rotacionado."""

    x: float
    y: float
    width: float
    height: float

    def clamped(self) -> "NormalizedRect":
        x = max(0.0, min(1.0, self.x))
        y = max(0.0, min(1.0, self.y))
        width = max(0.0, min(1.0 - x, self.width))
        height = max(0.0, min(1.0 - y, self.height))
        return NormalizedRect(x, y, width, height)

    def is_usable(self) -> bool:
        rect = self.clamped()
        return rect.width >= 0.01 and rect.height >= 0.01


@dataclass
class BlurState:
    """Fonte unica de verdade para o blur manual."""

    enabled: bool = False
    mode: str = "manual"
    intensity: float = 0.55
    region: Optional[NormalizedRect] = None

    def copy(self) -> "BlurState":
        region = None
        if self.region is not None:
            region = NormalizedRect(
                self.region.x,
                self.region.y,
                self.region.width,
                self.region.height
            )
        return BlurState(
            enabled=self.enabled,
            mode=self.mode,
            intensity=self.intensity,
            region=region
        )

    def has_effect(self) -> bool:
        return (
            self.enabled
            and self.mode == "manual"
            and self.intensity > 0
            and self.region is not None
            and self.region.is_usable()
        )

