"""Sample IIIF documents shared by the core and MCP test suites."""

V3_INFO = {
    "@context": "http://iiif.io/api/image/3/context.json",
    "id": "https://iiif.example.org/iiif/3/page1",
    "type": "ImageService3",
    "profile": "level2",
    "width": 4000,
    "height": 6000,
    "maxWidth": 3000,
    "sizes": [{"width": 500, "height": 750}],
}

V2_INFO = {
    "@context": "http://iiif.io/api/image/2/context.json",
    "@id": "https://iiif.example.org/iiif/2/page1",
    "profile": ["http://iiif.io/api/image/2/level1.json", {"formats": ["jpg"]}],
    "width": 2000,
    "height": 3000,
}

V3_MANIFEST = {
    "@context": "http://iiif.io/api/presentation/3/context.json",
    "id": "https://iiif.example.org/manifest.json",
    "type": "Manifest",
    "label": {"en": ["Test codex"]},
    "items": [
        {
            "id": "https://iiif.example.org/canvas/1",
            "type": "Canvas",
            "label": {"none": ["1r"]},
            "width": 2000,
            "height": 3000,
            "items": [
                {
                    "type": "AnnotationPage",
                    "items": [
                        {
                            "type": "Annotation",
                            "motivation": "painting",
                            "body": {
                                "id": "https://iiif.example.org/iiif/3/page1/full/max/0/default.jpg",
                                "type": "Image",
                                "service": [
                                    {
                                        "id": "https://iiif.example.org/iiif/3/page1",
                                        "type": "ImageService3",
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }
    ],
}

V2_MANIFEST = {
    "@context": "http://iiif.io/api/presentation/2/context.json",
    "@id": "https://iiif.example.org/v2/manifest.json",
    "label": "Old codex",
    "sequences": [
        {
            "canvases": [
                {
                    "@id": "https://iiif.example.org/v2/canvas/1",
                    "label": "1r",
                    "width": 1000,
                    "height": 1500,
                    "images": [
                        {"resource": {"service": {"@id": "https://iiif.example.org/iiif/2/page1"}}}
                    ],
                }
            ]
        }
    ],
}
