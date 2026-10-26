import pytest

from apud.iiif import Region, UnsupportedRequest, parse_info


def test_parse_v3(v3_info):
    service = parse_info(v3_info)
    assert (service.version, service.level) == (3, 2)
    assert service.max_width == 3000
    assert service.sizes == [(500, 750)]


def test_parse_v2_profile_list(v2_info):
    service = parse_info(v2_info)
    assert (service.version, service.level) == (2, 1)
    assert service.id == "https://iiif.example.org/iiif/2/page1"


def test_missing_profile_is_level0(v3_info):
    del v3_info["profile"]
    assert parse_info(v3_info).level == 0


def test_region_request_downscales_to_max_side(v3_info):
    request = parse_info(v3_info).region_request(Region(100, 200, 2000, 1000), max_side=1000)
    assert (
        request.url
        == "https://iiif.example.org/iiif/3/page1/100,200,2000,1000/1000,500/0/default.jpg"
    )
    assert request.scale == 0.5
    assert request.to_image(10, 20) == (120, 240)


def test_region_request_never_upscales(v3_info):
    request = parse_info(v3_info).region_request(Region(0, 0, 300, 200), max_side=2000)
    assert (request.width, request.height) == (300, 200)


def test_region_request_respects_server_limits(v3_info):
    v3_info["maxArea"] = 1_000_000
    request = parse_info(v3_info).region_request(Region(0, 0, 4000, 4000), max_side=5000)
    assert max(request.width, request.height) == 1000


def test_region_is_clamped_to_image(v3_info):
    request = parse_info(v3_info).region_request(Region(3900, 5900, 500, 500), max_side=2000)
    assert request.region == Region(3900, 5900, 100, 100)


def test_level0_rejects_regions(v3_info):
    v3_info["profile"] = "level0"
    with pytest.raises(UnsupportedRequest):
        parse_info(v3_info).region_request(Region(0, 0, 10, 10), max_side=100)


def test_invalid_region():
    with pytest.raises(ValueError):
        Region(0, 0, 0, 10)
