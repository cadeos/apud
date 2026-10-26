"""IIIF Presentation API: lenient extraction of canvases from v2 and v3 manifests.

Real-world manifests are often inconsistent (mixed v2/v3 keys, canvas sizes that differ from
the image), so this module reads only what it needs and does not validate the whole document.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apud.iiif.image import Region


@dataclass(frozen=True)
class Canvas:
    id: str
    width: int
    height: int
    label: str | None
    image_service: str | None


@dataclass(frozen=True)
class Manifest:
    id: str
    label: str | None
    canvases: list[Canvas]


def parse_manifest(data: dict[str, Any]) -> Manifest:
    manifest_id = data.get("id") or data.get("@id")
    if not manifest_id:
        raise ValueError("manifest has no id")
    if "items" in data:
        raw_canvases = data["items"]
        to_canvas = _canvas_v3
    else:
        sequences = data.get("sequences") or [{}]
        raw_canvases = sequences[0].get("canvases", [])
        to_canvas = _canvas_v2
    return Manifest(
        id=manifest_id,
        label=_label(data.get("label")),
        canvases=[to_canvas(c) for c in raw_canvases],
    )


def image_to_canvas(region: Region, image_width: int, image_height: int, canvas: Canvas) -> Region:
    """Rescale a region from image pixels to canvas coordinates (they can legitimately differ)."""
    sx = canvas.width / image_width
    sy = canvas.height / image_height
    return Region(
        round(region.x * sx), round(region.y * sy), round(region.w * sx), round(region.h * sy)
    )


def canvas_to_image(region: Region, image_width: int, image_height: int, canvas: Canvas) -> Region:
    """Rescale a region from canvas coordinates to image pixels."""
    sx = image_width / canvas.width
    sy = image_height / canvas.height
    return Region(
        round(region.x * sx), round(region.y * sy), round(region.w * sx), round(region.h * sy)
    )


def _canvas_v3(c: dict[str, Any]) -> Canvas:
    service = None
    for page in c.get("items", []):
        for anno in page.get("items", []):
            service = _service_id(anno.get("body", {}))
            if service:
                break
        if service:
            break
    return Canvas(c["id"], int(c["width"]), int(c["height"]), _label(c.get("label")), service)


def _canvas_v2(c: dict[str, Any]) -> Canvas:
    service = None
    for image in c.get("images", []):
        service = _service_id(image.get("resource", {}))
        if service:
            break
    return Canvas(c["@id"], int(c["width"]), int(c["height"]), _label(c.get("label")), service)


def _service_id(resource: dict[str, Any] | list[Any]) -> str | None:
    if isinstance(resource, list):
        resource = resource[0] if resource else {}
    services = resource.get("service", [])
    for service in services if isinstance(services, list) else [services]:
        if isinstance(service, dict) and (sid := service.get("id") or service.get("@id")):
            return sid
    return None


def _label(label: Any) -> str | None:
    # v3 language map {"en": ["..."]}, v2 plain string or list of {"@value": ...}
    if label is None:
        return None
    if isinstance(label, str):
        return label
    if isinstance(label, dict):
        for values in label.values():
            if values:
                return str(values[0])
        return None
    if isinstance(label, list) and label:
        first = label[0]
        return first.get("@value") if isinstance(first, dict) else str(first)
    return None
