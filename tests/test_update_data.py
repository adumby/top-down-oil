"""Offline tests for the data refresher (network calls are mocked)."""
import importlib.util
import io
from pathlib import Path

import pytest

from oilinfl.data import read_fred_csv

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("update_data", ROOT / "scripts" / "update_data.py")
ud = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ud)

FAKE = {
    "DCOILWTICO": "observation_date,DCOILWTICO\n2026-10-27,103.37\n2026-10-28,.\n",
    "DGASNYH": "observation_date,DGASNYH\n2026-10-27,2.819\n2026-10-28,2.8\n",
    "DDFUELNYH": "observation_date,DDFUELNYH\n2026-10-27,4.667\n2026-10-28,4.6\n",
    "GS2": "observation_date,GS2\n2026-09-01,4.65\n2026-10-01,4.74\n",
}


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def fake_net(monkeypatch):
    def urlopen(url, timeout=0):
        sid = url.split("id=")[-1]
        return _Resp(FAKE[sid].encode())
    monkeypatch.setattr(ud.urllib.request, "urlopen", urlopen)


def test_fetch_and_write_roundtrip(fake_net, tmp_path, monkeypatch):
    monkeypatch.setattr(ud, "RAW", tmp_path)
    (tmp_path / "fred").mkdir()
    s = ud.fetch_fred("GS2")
    ud.write_fred(s, "GS2")
    back = read_fred_csv(tmp_path / "fred" / "GS2.csv")
    assert back.iloc[-1] == 4.74 and back.name == "GS2"


def test_crack_spread_formula_matches_shipped_file(fake_net):
    c = ud.crack_spread()
    assert len(c) == 1                                  # the row with a missing WTI is dropped
    assert c["crack_321"].iloc[0] == pytest.approx(40.9, abs=0.01)   # value in data/raw/eia for 2026-10-27
