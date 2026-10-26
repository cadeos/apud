from apud.annotations import (
    annotation_page,
    decode_content_state,
    encode_content_state,
    transcription_annotation,
)
from apud.iiif import Region

CANVAS = "https://iiif.example.org/canvas/1"
MANIFEST = "https://iiif.example.org/manifest.json"


def test_transcription_annotation_targets_canvas_fragment():
    anno = transcription_annotation(
        "urn:a1", CANVAS, MANIFEST, Region(1, 2, 3, 4), "Nel mezzo", language="it"
    )
    assert anno["motivation"] == "supplementing"
    assert anno["body"] == {
        "type": "TextualBody",
        "value": "Nel mezzo",
        "format": "text/plain",
        "language": "it",
    }
    assert anno["target"]["source"]["id"] == CANVAS
    assert anno["target"]["source"]["partOf"] == [{"id": MANIFEST, "type": "Manifest"}]
    assert anno["target"]["selector"]["value"] == "xywh=1,2,3,4"


def test_annotation_page_wraps_items():
    page = annotation_page("urn:p", [{"id": "urn:a"}])
    assert page["type"] == "AnnotationPage" and page["items"] == [{"id": "urn:a"}]


def test_content_state_round_trip():
    encoded = encode_content_state(CANVAS, MANIFEST, Region(10, 20, 30, 40))
    assert "=" not in encoded and "+" not in encoded and "/" not in encoded
    state = decode_content_state(encoded)
    assert state["id"] == f"{CANVAS}#xywh=10,20,30,40"
    assert state["partOf"][0]["id"] == MANIFEST
