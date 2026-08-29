"""SGP4 verification against Vallado's published test vectors (satellite 00005
from the official SGP4-VER.TLE / tcppver.out distributed with Spacetrack Report
#3, Vallado 2006)."""
import numpy as np
import pytest

from app.domain import TLE
from app.services.propagate import SGP4Propagator, TwoBodyPropagator, apsis_altitudes_km

SAT5 = TLE(
    name="SGP4 VER 00005",
    line1="1 00005U 58002B   00179.78495062  .00000023  00000-0  28098-4 0  4753",
    line2="2 00005  34.2682 348.7242 1859667 331.7664  19.3264 10.82419157413667",
)

# (tsince_min, r_km, v_km_s). The tsince=0 row is the value published in
# tcppver.out (Vallado 2006). The 360/720 rows are the verified output of the
# reference python-sgp4 implementation (itself validated against tcppver) and
# serve as a regression guard on the absolute-epoch arithmetic.
REFERENCE = [
    (0.0,
     (7022.46529266, -1400.08296755, 0.03995155),
     (1.893841015, 6.405893759, 4.534807250)),
    (360.0,
     (-7154.03120202, -3783.17682504, -3536.19412294),
     (4.741887409, -4.151817765, -2.093935425)),
    (720.0,
     (-7134.59340119, 6531.68641334, 3260.27186483),
     (-4.113793027, -2.911922039, -2.557327851)),
]


@pytest.mark.parametrize("tsince,r_ref,v_ref", REFERENCE)
def test_sgp4_matches_vallado_vector(tsince, r_ref, v_ref):
    prop = SGP4Propagator()
    r, v = prop.states_at_minutes(SAT5, np.array([tsince]))
    np.testing.assert_allclose(r[0], r_ref, atol=1e-4)
    np.testing.assert_allclose(v[0], v_ref, atol=1e-7)


def test_apsis_altitudes_reasonable():
    perigee, apogee = apsis_altitudes_km(SAT5)
    # Eccentric orbit (e ~ 0.186): low perigee, much higher apogee.
    assert 500 < perigee < 900
    assert 3000 < apogee < 5000
    assert apogee > perigee + 2000


def test_twobody_energy_conserved():
    prop = TwoBodyPropagator()
    r0 = np.array([7000.0, 0.0, 0.0])
    v0 = np.array([0.0, 7.546, 0.0])
    eph = prop.propagate_state(r0, v0, 0.0, np.linspace(0, 6000, 25))
    mu = 398600.4418
    energy = 0.5 * np.sum(eph.v_km_s**2, axis=1) - mu / np.linalg.norm(eph.r_km, axis=1)
    assert np.ptp(energy) < 1e-6 * abs(energy[0])
