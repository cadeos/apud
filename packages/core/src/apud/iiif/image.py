"""IIIF Image API: parse info.json (v2 and v3) and plan region requests sized for a model.

Level 1+ servers cut regions themselves: one URL per request. Level 0 servers only serve
pre-rendered files, so a region is planned as the set of tiles that cover it (or, without
tiles, one of the declared full-image ``sizes``), to be stitched and cropped client-side.
"""

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
class Tile:
    """A pre-rendered file covering ``box`` (full-resolution pixels) at ``1 / factor`` scale."""

    url: str
    box: Region
    factor: float


@dataclass(frozen=True)
class TileSpec:
    width: int
    height: int
    scale_factors: tuple[int, ...]


@dataclass(frozen=True)
class RegionRequest:
    """How to obtain a region, and the scale needed to map model output back to the image.

    Exactly one of ``url`` (the server cuts the region) or ``tiles`` (stitch client-side,
    Level 0) is set.
    """

    region: Region
    width: int
    height: int
    url: str | None = None
    tiles: tuple[Tile, ...] = ()

    @property
    def urls(self) -> list[str]:
        return [self.url] if self.url else [t.url for t in self.tiles]

    @property
    def scale(self) -> float:
        """Returned pixels per full-resolution pixel (<= 1, never upscaled)."""
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
    tiles: list[TileSpec] = field(default_factory=list)
    max_width: int | None = None
    max_height: int | None = None
    max_area: int | None = None

    def region_request(self, region: Region, max_side: int, fmt: str = "jpg") -> RegionRequest:
        """Plan a region whose longer side is at most ``max_side``, honouring server limits."""
        region = region.clamp(self.width, self.height)
        if self.level >= 1:
            return self._server_side(region, max_side, fmt)
        w, h = _fit(region, max_side)
        if self.tiles:
            return RegionRequest(
                region, w, h, tiles=self._cover(region, max(region.w, region.h) / max_side, fmt)
            )
        if self.sizes:
            return RegionRequest(region, w, h, tiles=(self._from_sizes(w / region.w, fmt),))
        raise UnsupportedRequest("Level 0 service without tiles or sizes cannot serve regions")

    def _server_side(self, region: Region, max_side: int, fmt: str) -> RegionRequest:
        # Pixel regions and explicit w,h sizes: the forms required from Level 1 upward.
        limit = max_side
        if self.max_width is not None:
            limit = min(limit, self.max_width, self.max_height or self.max_width)
        if self.max_area is not None:
            limit = min(limit, math.isqrt(self.max_area))
        w, h = _fit(region, limit)
        url = f"{self.id.rstrip('/')}/{region.xywh}/{w},{h}/0/default.{fmt}"
        return RegionRequest(region, w, h, url=url)

    def _cover(self, region: Region, wanted_factor: float, fmt: str) -> tuple[Tile, ...]:
        """Tiles covering ``region`` at the coarsest scale that still has enough pixels."""
        spec = self.tiles[0]
        usable = [f for f in sorted(spec.scale_factors) if f <= max(1.0, wanted_factor)]
        factor = usable[-1] if usable else min(spec.scale_factors)
        step_w, step_h = spec.width * factor, spec.height * factor
        tiles = []
        for ty in range(region.y // step_h, (region.y + region.h - 1) // step_h + 1):
            for tx in range(region.x // step_w, (region.x + region.w - 1) // step_w + 1):
                x, y = tx * step_w, ty * step_h
                box = Region(x, y, min(step_w, self.width - x), min(step_h, self.height - y))
                size = (math.ceil(box.w / factor), math.ceil(box.h / factor))
                tiles.append(Tile(self._url(box, size, fmt), box, factor))
        return tuple(tiles)

    def _from_sizes(self, needed_scale: float, fmt: str) -> Tile:
        """The smallest declared full-image size with at least the needed resolution."""
        ordered = sorted(self.sizes)
        size = next((s for s in ordered if s[0] / self.width >= needed_scale), ordered[-1])
        factor = self.width / size[0]
        full = Region(0, 0, self.width, self.height)
        return Tile(self._url(full, size, fmt), full, factor)

    def _url(self, box: Region, size: tuple[int, int], fmt: str) -> str:
        whole = (box.x, box.y, box.w, box.h) == (0, 0, self.width, self.height)
        region = "full" if whole else box.xywh
        # Canonical size: "w,h" in Image API 3, "w," in Image API 2.
        size_param = f"{size[0]},{size[1]}" if self.version >= 3 else f"{size[0]},"
        return f"{self.id.rstrip('/')}/{region}/{size_param}/0/default.{fmt}"


def _fit(region: Region, limit: int) -> tuple[int, int]:
    factor = min(1.0, limit / max(region.w, region.h))
    return max(1, math.floor(region.w * factor)), max(1, math.floor(region.h * factor))


def parse_info(info: dict[str, Any]) -> ImageService:
    """Parse an Image API v2 or v3 info.json document."""
    context = info.get("@context", "")
    contexts = context if isinstance(context, list) else [context]
    version = 3 if any("image/3" in str(c) for c in contexts) else 2
    service_id = info.get("id") or info.get("@id")
    if not service_id:
        raise ValueError("info.json has no id")
    sizes = [(s["width"], s["height"]) for s in info.get("sizes", [])]
    tiles = [
        TileSpec(t["width"], t.get("height", t["width"]), tuple(t.get("scaleFactors", [1])))
        for t in info.get("tiles", [])
    ]
    return ImageService(
        id=service_id,
        width=int(info["width"]),
        height=int(info["height"]),
        version=version,
        level=_parse_level(info.get("profile")),
        sizes=sizes,
        tiles=tiles,
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
