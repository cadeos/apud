import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from samples import V2_INFO, V2_MANIFEST, V3_INFO, V3_MANIFEST


@pytest.fixture
def v3_info():
    return dict(V3_INFO)


@pytest.fixture
def v2_info():
    return dict(V2_INFO)


@pytest.fixture
def v3_manifest():
    return V3_MANIFEST


@pytest.fixture
def v2_manifest():
    return V2_MANIFEST
