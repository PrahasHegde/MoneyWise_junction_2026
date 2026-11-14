import os
import pathlib
import sys

# Deterministic, offline test environment (set before the app is imported).
os.environ["COACH_PROVIDER"] = "offline"
os.environ["COACH_TODAY"] = "2026-11-14"
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from coach import analytics as A  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_overrides(tmp_path, monkeypatch):
    """Never touch the real data/overrides.json from tests."""
    monkeypatch.setattr(A, "OVERRIDES_FILE", tmp_path / "overrides.json")
    A._CACHE.clear()
    yield
    A._CACHE.clear()
