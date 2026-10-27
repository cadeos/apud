"""Thin HTTP client for IIIF endpoints."""

from __future__ import annotations

import io
from typing import Any

import httpx
from PIL import Image

from apud import __version__
from apud.iiif.image import ImageService, Region, RegionRequest, parse_info
from apud.iiif.manifest import Manifest, parse_manifest

USER_AGENT = f"apud/{__version__} (+https://github.com/cadeos/apud)"
JPEG_QUALITY = 90


class IIIFClient:
    def __init__(self, timeout: float = 30.0, client: httpx.Client | None = None) -> None:
        self._http = client or httpx.Client(
            timeout=timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT}
        )

    def __enter__(self) -> IIIFClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def _json(self, url: str) -> dict[str, Any]:
        response = self._http.get(url)
        response.raise_for_status()
        return response.json()

    def _bytes(self, url: str) -> bytes:
        response = self._http.get(url)
        response.raise_for_status()
        return response.content

    def manifest(self, url: str) -> Manifest:
        return parse_manifest(self._json(url))

    def image_service(self, service_id: str) -> ImageService:
        url = (
            service_id
            if service_id.endswith("info.json")
            else f"{service_id.rstrip('/')}/info.json"
        )
        return parse_info(self._json(url))

    def region(
        self, service: ImageService, region: Region, max_side: int
    ) -> tuple[RegionRequest, bytes]:
        """Fetch a region as JPEG bytes, stitching Level 0 tiles client-side when needed."""
        request = service.region_request(region, max_side)
        if request.url:
            return request, self._bytes(request.url)
        return request, _encode(self._stitch(request))

    def _stitch(self, request: RegionRequest) -> Image.Image:
        # Tiles share one scale factor; place them on a mosaic in tile pixels, then crop the
        # region out of it and resize to the requested output size.
        factor = request.tiles[0].factor
        left = min(t.box.x for t in request.tiles)
        top = min(t.box.y for t in request.tiles)
        right = max(t.box.x + t.box.w for t in request.tiles)
        bottom = max(t.box.y + t.box.h for t in request.tiles)
        mosaic = Image.new("RGB", (_px(right - left, factor), _px(bottom - top, factor)))
        for tile in request.tiles:
            with Image.open(io.BytesIO(self._bytes(tile.url))) as image:
                mosaic.paste(
                    image.convert("RGB"),
                    (round((tile.box.x - left) / factor), round((tile.box.y - top) / factor)),
                )
        r = request.region
        crop = mosaic.crop(
            (
                round((r.x - left) / factor),
                round((r.y - top) / factor),
                round((r.x + r.w - left) / factor),
                round((r.y + r.h - top) / factor),
            )
        )
        return crop.resize((request.width, request.height), Image.Resampling.LANCZOS)


def _px(full_resolution: int, factor: float) -> int:
    return max(1, round(full_resolution / factor))


def _encode(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=JPEG_QUALITY)
    return buffer.getvalue()
