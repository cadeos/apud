"""Thin HTTP client for IIIF endpoints."""

from __future__ import annotations

from typing import Any

import httpx

from apud import __version__
from apud.iiif.image import ImageService, Region, RegionRequest, parse_info
from apud.iiif.manifest import Manifest, parse_manifest

USER_AGENT = f"apud/{__version__} (+https://github.com/cadeos/apud)"


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
        request = service.region_request(region, max_side)
        response = self._http.get(request.url)
        response.raise_for_status()
        return request, response.content
