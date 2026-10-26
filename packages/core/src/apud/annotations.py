"""W3C Web Annotations anchored to IIIF canvases, plus IIIF Content State links for citation."""

from __future__ import annotations

import base64
import json
from typing import Any
from urllib.parse import quote, unquote

from apud.iiif.image import Region

_FRAGMENT_SPEC = "http://www.w3.org/TR/media-frags/"


def _target(canvas_id: str, manifest_id: str, region: Region) -> dict[str, Any]:
    return {
        "type": "SpecificResource",
        "source": {
            "id": canvas_id,
            "type": "Canvas",
            "partOf": [{"id": manifest_id, "type": "Manifest"}],
        },
        "selector": {
            "type": "FragmentSelector",
            "conformsTo": _FRAGMENT_SPEC,
            "value": f"xywh={region.xywh}",
        },
    }


def transcription_annotation(
    annotation_id: str,
    canvas_id: str,
    manifest_id: str,
    region: Region,
    text: str,
    *,
    language: str | None = None,
    generator: str | None = None,
) -> dict[str, Any]:
    """A transcription of ``region`` (canvas coordinates) as a Presentation 3 annotation."""
    body: dict[str, Any] = {"type": "TextualBody", "value": text, "format": "text/plain"}
    if language:
        body["language"] = language
    annotation: dict[str, Any] = {
        "id": annotation_id,
        "type": "Annotation",
        "motivation": "supplementing",
        "body": body,
        "target": _target(canvas_id, manifest_id, region),
    }
    if generator:
        annotation["generator"] = generator
    return annotation


def annotation_page(page_id: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "@context": "http://iiif.io/api/presentation/3/context.json",
        "id": page_id,
        "type": "AnnotationPage",
        "items": items,
    }


def encode_content_state(canvas_id: str, manifest_id: str, region: Region) -> str:
    """Encode a IIIF Content State pointing at a canvas region, for ``?iiif-content=`` links."""
    state = {
        "id": f"{canvas_id}#xywh={region.xywh}",
        "type": "Canvas",
        "partOf": [{"id": manifest_id, "type": "Manifest"}],
    }
    uri_encoded = quote(json.dumps(state, separators=(",", ":")), safe="-_.!~*'()")
    return base64.urlsafe_b64encode(uri_encoded.encode()).decode().rstrip("=")


def decode_content_state(encoded: str) -> dict[str, Any]:
    padded = encoded + "=" * (-len(encoded) % 4)
    return json.loads(unquote(base64.urlsafe_b64decode(padded).decode()))
