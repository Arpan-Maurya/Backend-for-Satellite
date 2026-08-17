"""
Advanced tests for orbital calculations, SGP4 propagation, and broad-phase pair filtering.
"""

from datetime import datetime, timezone
import pytest
from app.core.orbital_calc import (
    propagate_sgp4,
    compute_minimum_separation,
    filter_potential_conjunction_pairs,
    _datetime_to_jd,
    OrbitalElements,
)
from app.core.tle_parser import parse_tle
from app.core.exceptions import OrbitalCalculationError

SAMPLE_TLE_1_LINE1 = "1 25544U 98067A   24001.50000000  .00016717  00000-0  10270-3 0  9021"
SAMPLE_TLE_1_LINE2 = "2 25544  51.6400 208.9163 0006703 358.1484  30.8603 15.50216498484890"

SAMPLE_TLE_2_LINE1 = "1 48274U 21035A   24001.50000000  .00002000  00000-0  15000-3 0  9999"
SAMPLE_TLE_2_LINE2 = "2 48274  53.0500 120.0000 0001000  90.0000 270.0000 15.06400000100009"


def test_datetime_to_jd():
    dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    jd, fr = _datetime_to_jd(dt)
    assert jd > 2400000.0
    assert 0.0 <= fr <= 1.0


def test_propagate_sgp4():
    dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    r, v = propagate_sgp4(SAMPLE_TLE_1_LINE1, SAMPLE_TLE_1_LINE2, dt)
    assert len(r) == 3
    assert len(v) == 3
    assert all(isinstance(x, float) for x in r)
    assert all(isinstance(x, float) for x in v)


def test_compute_minimum_separation():
    msd_m = compute_minimum_separation(
        SAMPLE_TLE_1_LINE1, SAMPLE_TLE_1_LINE2,
        SAMPLE_TLE_2_LINE1, SAMPLE_TLE_2_LINE2,
        time_steps=20, horizon_hours=1.0,
    )
    assert isinstance(msd_m, float)
    assert msd_m > 0


def test_filter_potential_conjunction_pairs():
    # Sat 1: 400 - 420 km altitude
    sat1 = OrbitalElements(
        norad_id="25544",
        semi_major_axis_km=6791.0,
        eccentricity=0.001,
        inclination_deg=51.6,
        raan_deg=200.0,
        arg_perigee_deg=30.0,
        mean_motion_revday=15.5,
        apogee_alt_km=420.0,
        perigee_alt_km=400.0,
    )
    # Sat 2: 410 - 430 km altitude (Overlaps with Sat 1)
    sat2 = OrbitalElements(
        norad_id="48274",
        semi_major_axis_km=6798.0,
        eccentricity=0.001,
        inclination_deg=53.0,
        raan_deg=120.0,
        arg_perigee_deg=90.0,
        mean_motion_revday=15.1,
        apogee_alt_km=430.0,
        perigee_alt_km=410.0,
    )
    # Sat 3: 1200 - 1220 km altitude (Disjoint from Sat 1 and Sat 2)
    sat3 = OrbitalElements(
        norad_id="99999",
        semi_major_axis_km=7588.0,
        eccentricity=0.001,
        inclination_deg=86.0,
        raan_deg=45.0,
        arg_perigee_deg=180.0,
        mean_motion_revday=13.0,
        apogee_alt_km=1220.0,
        perigee_alt_km=1200.0,
    )

    candidates = filter_potential_conjunction_pairs([sat1, sat2, sat3], altitude_threshold_km=20.0)
    # Only Sat 1 and Sat 2 should overlap; Sat 3 is 700km higher
    assert len(candidates) == 1
    assert candidates[0] == (sat1, sat2)


def test_filter_potential_conjunction_pairs_empty():
    assert filter_potential_conjunction_pairs([]) == []
    sat = OrbitalElements(
        norad_id="25544",
        semi_major_axis_km=6791.0, eccentricity=0.001, inclination_deg=51.6,
        raan_deg=200.0, arg_perigee_deg=30.0,
        mean_motion_revday=15.5, apogee_alt_km=420.0, perigee_alt_km=400.0,
    )
    assert filter_potential_conjunction_pairs([sat]) == []
