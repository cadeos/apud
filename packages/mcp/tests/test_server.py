import httpx
import pytest

from apud.client import IIIFClient
from samples import V3_INFO, V3_MANIFEST

MANIFEST_URL = "https://iiif.example.org/manifest.json"
CANVAS = "https://iiif.example.org/canvas/1"


@pytest.fixture
def server(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == MANIFEST_URL:
            return httpx.Response(200, json=V3_MANIFEST)
        if url.endswith("info.json"):
            return httpx.Response(200, json=V3_INFO)
        if url.endswith("default.jpg"):
            return httpx.Response(200, content=b"\xff\xd8fakejpeg")
        return httpx.Response(404)

    import apud_mcp.server as module

    monkeypatch.setattr(
        module,
        "IIIFClient",
        lambda: IIIFClient(client=httpx.Client(transport=httpx.MockTransport(handler))),
    )
    return module


def test_describe_manifest(server):
    result = server.describe_manifest(MANIFEST_URL)
    assert result["total_canvases"] == 1
    assert result["canvases"][0]["id"] == CANVAS


def test_view_region_maps_canvas_to_image(server):
    image, meta = server.view_region(MANIFEST_URL, CANVAS, 100, 100, 500, 250, max_side=500)
    # canvas 2000x3000 -> image 4000x6000, so the image region is doubled and then halved to fit
    assert meta["source_urls"] == [
        "https://iiif.example.org/iiif/3/page1/200,200,1000,500/500,250/0/default.jpg"
    ]
    assert meta["to_canvas"] == "canvas_x = 100 + crop_x * 1.0000; canvas_y = 100 + crop_y * 1.0000"


def test_annotate_transcription(server):
    result = server.annotate_transcription(
        MANIFEST_URL, CANVAS, 10, 20, 300, 40, "In principio", "la"
    )
    assert result["annotation"]["target"]["selector"]["value"] == "xywh=10,20,300,40"
    assert result["content_state"]
