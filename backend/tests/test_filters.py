"""ApsisFilter: synthetic pairs whose answer is known by hand."""
from app.services.filters import AcceptAllFilter, ApsisFilter
from tests.conftest import make_object


def test_overlapping_altitude_bands_are_kept():
    f = ApsisFilter(pad_km=0.0)
    # LEO object 500-550 km vs another 520-600 km: bands overlap -> keep.
    a = make_object(1, perigee_alt_km=500, apogee_alt_km=550)
    b = make_object(2, perigee_alt_km=520, apogee_alt_km=600)
    assert f.keep_pair(a, b) is True
    assert f.keep_pair(b, a) is True          # symmetric


def test_disjoint_altitude_bands_are_dropped():
    f = ApsisFilter(pad_km=0.0)
    # 400-450 km LEO vs a 1200-1250 km orbit: no radial overlap -> drop.
    a = make_object(1, perigee_alt_km=400, apogee_alt_km=450)
    b = make_object(2, perigee_alt_km=1200, apogee_alt_km=1250)
    assert f.keep_pair(a, b) is False


def test_pad_widens_the_band():
    a = make_object(1, perigee_alt_km=400, apogee_alt_km=450)
    b = make_object(2, perigee_alt_km=470, apogee_alt_km=500)
    assert ApsisFilter(pad_km=0.0).keep_pair(a, b) is False
    assert ApsisFilter(pad_km=25.0).keep_pair(a, b) is True    # 450+25 >= 470-25


def test_eccentric_orbit_crossing_a_circular_one_is_kept():
    # Molniya-like 500 x 39000 crosses a 800 km circular orbit radially.
    a = make_object(1, perigee_alt_km=500, apogee_alt_km=39000)
    b = make_object(2, perigee_alt_km=790, apogee_alt_km=810)
    assert ApsisFilter(pad_km=0.0).keep_pair(a, b) is True


def test_accept_all_is_a_valid_substitute():
    f = AcceptAllFilter()
    a = make_object(1, perigee_alt_km=400, apogee_alt_km=450)
    b = make_object(2, perigee_alt_km=9000, apogee_alt_km=9100)
    assert f.keep_pair(a, b) is True
