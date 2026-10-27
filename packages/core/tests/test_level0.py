import io
import re

import httpx
import pytest
from PIL import Image, ImageDraw

from apud.client import IIIFClient
from apud.iiif import Region, parse_info

BASE = "https://static.example.org/iiif/p1"


def info(version=3, tiles=True, sizes=None, width=1100, height=700):
    data = {
        "@context": f"http://iiif.io/api/image/{version}/context.json",
        "id" if version == 3 else "@id": BASE,
        "profile": "level0" if version == 3 else ["http://iiif.io/api/image/2/level0.json"],
        "width": width,
        "height": height,
    }
    if tiles:
        data["tiles"] = [{"width": 512, "scaleFactors": [1, 2, 4]}]
    if sizes:
        data["sizes"] = [{"width": w, "height": h} for w, h in sizes]
    return data


def test_tiles_cover_region_at_full_resolution():
    request = parse_info(info()).region_request(Region(400, 100, 300, 200), max_side=1000)
    assert request.url is None and (request.width, request.height) == (300, 200)
    assert request.urls == [
        f"{BASE}/0,0,512,512/512,512/0/default.jpg",
        f"{BASE}/512,0,512,512/512,512/0/default.jpg",
    ]


def test_coarser_scale_factor_when_output_is_small():
    request = parse_info(info()).region_request(Region(400, 100, 300, 200), max_side=100)
    assert (request.width, request.height) == (100, 66)
    assert request.urls == [f"{BASE}/0,0,1024,700/512,350/0/default.jpg"]
    assert request.tiles[0].factor == 2


def test_whole_image_uses_full_region_and_v2_size_syntax():
    request = parse_info(info(version=2)).region_request(Region(0, 0, 1100, 700), max_side=275)
    assert request.urls == [f"{BASE}/full/275,/0/default.jpg"]


def test_sizes_fallback_picks_smallest_sufficient_size():
    service = parse_info(info(tiles=False, sizes=[(275, 175), (550, 350), (1100, 700)]))
    request = service.region_request(Region(0, 0, 1100, 700), max_side=500)
    assert request.urls == [f"{BASE}/full/550,350/0/default.jpg"]


def source_image(width=1100, height=700):
    image = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(image)
    for x in range(width):  # smooth gradient, so JPEG artefacts stay small
        draw.line([(x, 0), (x, height)], fill=(x * 255 // width, 90, 255 - x * 255 // width))
    for y in range(0, height, 60):  # sharp horizontal bands reveal any vertical misalignment
        draw.rectangle([0, y, width, y + 20], fill=(20, 20, 20))
    for x in range(0, width, 80):  # and vertical bars any horizontal one
        draw.rectangle([x, 0, x + 24, height], fill=(240, 240, 240))
    return image


def level0_server(image):
    """Serve exactly the files a static Level 0 export would contain."""
    pattern = re.compile(r"/iiif/p1/(full|\d+,\d+,\d+,\d+)/(\d+),(\d*)/0/default\.jpg$")
    requested = []

    def handler(request):
        match = pattern.search(request.url.path)
        if not match:
            return httpx.Response(404)
        requested.append(request.url.path)
        region, w, h = match.groups()
        x, y, rw, rh = (0, 0, *image.size) if region == "full" else map(int, region.split(","))
        w = int(w)
        h = int(h) if h else round(rh * w / rw)
        tile = image.crop((x, y, x + rw, y + rh)).resize((w, h), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        tile.save(buffer, "JPEG", quality=95)
        return httpx.Response(200, content=buffer.getvalue())

    return httpx.Client(transport=httpx.MockTransport(handler)), requested


def mean_abs_diff(a, b):
    left, right = a.tobytes(), b.tobytes()
    return sum(abs(p - q) for p, q in zip(left, right, strict=True)) / len(left)


@pytest.mark.parametrize(
    ("region", "max_side"),
    [
        (Region(400, 100, 300, 200), 1000),  # two tiles, full resolution
        (Region(450, 400, 600, 300), 1000),  # four tiles, partial edge tiles
        (Region(100, 50, 900, 600), 250),  # coarser scale factor
    ],
)
def test_stitched_region_matches_direct_crop(region, max_side):
    image = source_image()
    http, requested = level0_server(image)
    service = parse_info(info())
    with IIIFClient(client=http) as client:
        request, data = client.region(service, region, max_side)
    stitched = Image.open(io.BytesIO(data)).convert("RGB")
    assert stitched.size == (request.width, request.height)
    assert len(requested) == len(request.tiles)

    # The remaining error is JPEG noise on sharp edges; alignment must be exact: the source
    # crop at offset (0, 0) has to match better than any crop shifted by a pixel or two.
    def error(dx, dy):
        box = (region.x + dx, region.y + dy, region.x + region.w + dx, region.y + region.h + dy)
        return mean_abs_diff(
            stitched, image.crop(box).resize(stitched.size, Image.Resampling.LANCZOS)
        )

    aligned = error(0, 0)
    assert aligned < 6
    assert all(
        aligned < error(dx, dy) for dx in (-2, -1, 0, 1, 2) for dy in (-2, -1, 0, 1, 2) if dx or dy
    )
