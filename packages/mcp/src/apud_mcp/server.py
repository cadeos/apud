"""MCP server: lets an agent look at IIIF canvas regions and emit citable, anchored transcriptions.

All coordinates exchanged with the model are canvas coordinates, so annotations and citations
stay valid even when the served image size differs from the canvas size.
"""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import Image, MCPServer

from apud.annotations import encode_content_state, transcription_annotation
from apud.client import IIIFClient
from apud.iiif import Canvas, Region, canvas_to_image

# Keeps a JPEG crop comfortably under typical MCP client result limits (~1 MB).
DEFAULT_MAX_SIDE = 1568

server = MCPServer(
    name="apud",
    instructions=(
        "Work on IIIF manuscripts with verifiable citations. Use describe_manifest to list "
        "canvases, view_region to look at a canvas area at full detail, and "
        "annotate_transcription to record what you read, anchored to canvas coordinates."
    ),
)


def _find_canvas(manifest_url: str, canvas_id: str, client: IIIFClient) -> tuple[str, Canvas]:
    manifest = client.manifest(manifest_url)
    for canvas in manifest.canvases:
        if canvas.id == canvas_id:
            return manifest.id, canvas
    raise ValueError(f"canvas {canvas_id} not found in {manifest_url}")


@server.tool()
def describe_manifest(manifest_url: str, offset: int = 0, limit: int = 50) -> dict[str, Any]:
    """List the canvases of a IIIF manifest (id, label, size), paginated."""
    with IIIFClient() as client:
        manifest = client.manifest(manifest_url)
    canvases = manifest.canvases[offset : offset + limit]
    return {
        "manifest": manifest.id,
        "label": manifest.label,
        "total_canvases": len(manifest.canvases),
        "canvases": [
            {"id": c.id, "label": c.label, "width": c.width, "height": c.height} for c in canvases
        ],
    }


@server.tool()
def view_region(
    manifest_url: str,
    canvas_id: str,
    x: int,
    y: int,
    w: int,
    h: int,
    max_side: int = DEFAULT_MAX_SIDE,
) -> list[Any]:
    """Fetch a canvas region (canvas coordinates) at the best resolution the server allows.

    Returns the image and the mapping from crop pixels back to canvas coordinates.
    """
    with IIIFClient() as client:
        _, canvas = _find_canvas(manifest_url, canvas_id, client)
        if canvas.image_service is None:
            raise ValueError("canvas has no IIIF image service")
        service = client.image_service(canvas.image_service)
        image_region = canvas_to_image(Region(x, y, w, h), service.width, service.height, canvas)
        request, data = client.region(service, image_region, max_side)
    canvas_per_crop_px = (canvas.width / service.width) / request.scale
    return [
        Image(data=data, format="jpeg"),
        {
            "canvas_region": {"x": x, "y": y, "w": w, "h": h},
            "crop_size": {"width": request.width, "height": request.height},
            "to_canvas": (
                f"canvas_x = {x} + crop_x * {canvas_per_crop_px:.4f}; "
                f"canvas_y = {y} + crop_y * {canvas_per_crop_px:.4f}"
            ),
            "source_urls": request.urls,
        },
    ]


@server.tool()
def annotate_transcription(
    manifest_url: str,
    canvas_id: str,
    x: int,
    y: int,
    w: int,
    h: int,
    text: str,
    language: str | None = None,
) -> dict[str, Any]:
    """Record a transcription of a canvas region as a W3C annotation with a citable link."""
    with IIIFClient() as client:
        manifest_id, canvas = _find_canvas(manifest_url, canvas_id, client)
    region = Region(x, y, w, h).clamp(canvas.width, canvas.height)
    annotation = transcription_annotation(
        annotation_id=f"{canvas.id}/apud/{region.xywh}",
        canvas_id=canvas.id,
        manifest_id=manifest_id,
        region=region,
        text=text,
        language=language,
        generator="apud-mcp",
    )
    return {
        "annotation": annotation,
        "content_state": encode_content_state(canvas.id, manifest_id, region),
    }


def main() -> None:
    server.run()


if __name__ == "__main__":
    main()
