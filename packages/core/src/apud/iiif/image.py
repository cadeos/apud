"""IIIF Image API: parse info.json (v2 and v3) and build region requests sized for a model."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

_LEVEL_RE = re.compile(r"level([012])")


class UnsupportedRequest(ValueError):
    """The image service cannot serve the request at its declared compliance level."""


@dataclass(frozen=True)
class Region:
    """A rectangle in full-resolution image pixels."""

    x: int
    y: int
    w: int
    h: int

    def __post_init__(self) -> None:
        if self.w <= 0 or self.h <= 0:
            raise ValueError(f"region must have positive size, got {self.w}x{self.h}")
        if self.x < 0 or self.y < 0:
            raise ValueError(f"region origin must be non-negative, got {self.x},{self.y}")

    def clamp(self, width: int, height: int) -> Region:
        """Crop the region to the image bounds, as an IIIF server would."""
        if self.x >= width or self.y >= height:
            raise ValueError("region lies entirely outside the image")
        return Region(self.x, self.y, min(self.w, width - self.x), min(self.h, height - self.y))

    @property
    def xywh(self) -> str:
        return f"{self.x},{self.y},{self.w},{self.h}"


@dataclass(frozen=True)
class RegionRequest:
    """A ready-to-fetch region URL plus the scale needed to map model output back to the image."""

    url: str
    region: Region
    width: int
    height: int

    @property
    def scale(self) -> float:
        """Requested pixels per full-resolution pixel (<= 1, servers are never asked to upscale)."""
        return self.width / self.region.w

    def to_image(self, x: float, y: float) -> tuple[float, float]:
        """Map a point in the returned crop to full-resolution image coordinates."""
        return self.region.x + x / self.scale, self.region.y + y / self.scale


@dataclass(frozen=True)
class ImageService:
    id: str
    width: int
    height: int
    version: int
    level: int
    sizes: list[tuple[int, int]] = field(default_factory=list)
    max_width: int | None = None
    max_height: int | None = None
    max_area: int | None = None

    def region_request(self, region: Region, max_side: int, fmt: str = "jpg") -> RegionRequest:
        """Build a region URL whose longer side is at most ``max_side``, honouring server limits.

        Uses pixel regions and explicit ``w,h`` sizes, the forms required from Level 1 upward.
        """
        if self.level < 1:
            raise UnsupportedRequest(
                "Level 0 services do not support region requests; stitch tiles or use `sizes`"
            )
        region = region.clamp(self.width, self.height)
        limit = max_side
        if self.max_width is not None:
            limit = min(limit, self.max_width, self.max_height or self.max_width)
        if self.max_area is not None:
            limit = min(limit, math.isqrt(self.max_area))
        factor = min(1.0, limit / max(region.w, region.h))
        w = max(1, math.floor(region.w * factor))
        h = max(1, math.floor(region.h * factor))
        url = f"{self.id.rstrip('/')}/{region.xywh}/{w},{h}/0/default.{fmt}"
        return RegionRequest(url=url, region=region, width=w, height=h)


def parse_info(info: dict[str, Any]) -> ImageService:
    """Parse an Image API v2 or v3 info.json document."""
    context = info.get("@context", "")
    contexts = context if isinstance(context, list) else [context]
    version = 3 if any("image/3" in str(c) for c in contexts) else 2
    service_id = info.get("id") or info.get("@id")
    if not service_id:
        raise ValueError("info.json has no id")
    sizes = [(s["width"], s["height"]) for s in info.get("sizes", [])]
    return ImageService(
        id=service_id,
        width=int(info["width"]),
        height=int(info["height"]),
        version=version,
        level=_parse_level(info.get("profile")),
        sizes=sizes,
        max_width=info.get("maxWidth"),
        max_height=info.get("maxHeight"),
        max_area=info.get("maxArea"),
    )


def _parse_level(profile: Any) -> int:
    # v3: "level2"; v2: ["http://iiif.io/api/image/2/level2.json", {...}]
    candidates = profile if isinstance(profile, list) else [profile]
    for candidate in candidates:
        if isinstance(candidate, str) and (match := _LEVEL_RE.search(candidate)):
            return int(match.group(1))
    return 0
