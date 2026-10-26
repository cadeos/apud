from apud.iiif import Region, canvas_to_image, image_to_canvas, parse_manifest


def test_parse_v3_manifest(v3_manifest):
    manifest = parse_manifest(v3_manifest)
    assert manifest.label == "Test codex"
    [canvas] = manifest.canvases
    assert canvas.label == "1r"
    assert canvas.image_service == "https://iiif.example.org/iiif/3/page1"


def test_parse_v2_manifest(v2_manifest):
    manifest = parse_manifest(v2_manifest)
    [canvas] = manifest.canvases
    assert (canvas.id, canvas.width, canvas.height) == (
        "https://iiif.example.org/v2/canvas/1",
        1000,
        1500,
    )
    assert canvas.image_service == "https://iiif.example.org/iiif/2/page1"


def test_canvas_image_round_trip(v3_manifest):
    [canvas] = parse_manifest(v3_manifest).canvases  # 2000x3000 canvas
    image_region = canvas_to_image(Region(100, 150, 200, 300), 4000, 6000, canvas)
    assert image_region == Region(200, 300, 400, 600)
    assert image_to_canvas(image_region, 4000, 6000, canvas) == Region(100, 150, 200, 300)
