# apud

**IIIF-grounded, citable vision for historical documents.**

Vision-language models can read manuscripts, but they cannot say *where* they read what they
report, and their answers cannot be checked by a scholar. `apud` sits between IIIF collections
and models:

- fetches canvas regions from any IIIF Image API server at the best resolution the server and
  the model allow (Image API v2/v3, Presentation v2/v3, lenient parsing of real-world manifests);
- keeps every model output anchored to **canvas coordinates**, even when the served image size
  differs from the canvas;
- emits **W3C Web Annotations** (`xywh` fragment selectors) and **IIIF Content State** links, so
  every transcription can be opened at the exact spot in Mirador or any IIIF viewer.

> *apud* (Latin, "in the work of") is how philologists cite a source they read in someone
> else's text.

Status: pre-alpha.

## Packages

| Package | Path | What it is |
|---|---|---|
| `apud` | [`packages/core`](packages/core) | Python library: IIIF parsing, region requests, annotations, citations |
| `apud-mcp` | [`packages/mcp`](packages/mcp) | MCP server exposing `apud` to agents |

The benchmark lives in a separate repository: [apud-bench](https://github.com/cadeos/apud-bench).

## Quick look

```python
from apud.client import IIIFClient
from apud.iiif import Region, canvas_to_image

with IIIFClient() as iiif:
    manifest = iiif.manifest("https://www.e-codices.unifr.ch/metadata/iiif/csg-0390/manifest.json")
    canvas = manifest.canvases[10]
    service = iiif.image_service(canvas.image_service)
    region = canvas_to_image(Region(200, 300, 800, 400), service.width, service.height, canvas)
    request, jpeg = iiif.region(service, region, max_side=1568)
```

## MCP server

```bash
uvx apud-mcp
```

Tools: `describe_manifest`, `view_region`, `annotate_transcription`.

## Development

```bash
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

## License

Apache-2.0. See [CITATION.cff](CITATION.cff) for how to cite.
