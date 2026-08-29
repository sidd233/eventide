"""CelesTrakTLESource fallback behaviour. CelesTrak blocks many datacenter IP
ranges, so a deployed instance must degrade to a bundled snapshot rather than
500 on the first request."""
import httpx
import pytest

from app.services.tle_fetch import CelesTrakTLESource


def _blocked_client() -> httpx.Client:
    def handler(request):
        raise httpx.ConnectTimeout("simulated datacenter block", request=request)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_falls_back_to_bootstrap_when_celestrak_unreachable(fixture_tle_path):
    src = CelesTrakTLESource(
        groups=["stations"], client=_blocked_client(), bootstrap_path=fixture_tle_path
    )
    tles = src.fetch()
    assert len(tles) > 100
    assert src.served_stale is True
    assert "ConnectTimeout" in (src.last_error or "")

    # A second call inside the TTL serves the same bundled set, still flagged stale.
    again = src.fetch()
    assert len(again) == len(tles)
    assert src.served_stale is True


def test_raises_when_unreachable_and_no_bootstrap():
    src = CelesTrakTLESource(groups=["stations"], client=_blocked_client())
    with pytest.raises(httpx.ConnectTimeout):
        src.fetch()


def test_bundled_bootstrap_snapshot_is_present_and_parseable():
    from pathlib import Path

    from app.services.tle_fetch import parse_tle_text

    path = Path(__file__).resolve().parents[1] / "app" / "data" / "bootstrap_tles.txt"
    assert path.is_file(), "bundled TLE snapshot missing"
    tles = parse_tle_text(path.read_text())
    assert len(tles) > 500
    names = " ".join(t.name for t in tles).upper()
    assert "ISS" in names and "FENGYUN 1C DEB" in names
