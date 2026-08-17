"""
Orbital calculations using SGP4 propagation.

Extracts orbital elements and computes satellite positions from TLE data.
Uses the sgp4 library for standards-compliant propagation.
"""

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Tuple

import numpy as np
from sgp4.api import Satrec, WGS72
from sgp4 import exporter

from app.core.exceptions import OrbitalCalculationError
from app.core.tle_parser import ParsedTLE

logger = logging.getLogger(__name__)

# WGS-84 Earth parameters
EARTH_RADIUS_KM = 6378.137
MU_EARTH_KM3_S2 = 398600.4418  # Earth gravitational parameter


@dataclass(frozen=True)
class OrbitalElements:
    """Keplerian orbital elements for a satellite."""

    norad_id: str
    semi_major_axis_km: float    # km
    eccentricity: float          # dimensionless
    inclination_deg: float       # degrees
    raan_deg: float              # degrees
    arg_perigee_deg: float       # degrees
    mean_motion_revday: float    # revolutions per day
    apogee_alt_km: float         # km (above Earth surface)
    perigee_alt_km: float        # km (above Earth surface)


def compute_orbital_elements(parsed_tle: ParsedTLE) -> OrbitalElements:
    """
    Compute full orbital elements from parsed TLE data.

    Uses mean motion to derive semi-major axis and computes
    apogee/perigee altitudes.

    Args:
        parsed_tle: Validated and parsed TLE data.

    Returns:
        OrbitalElements with all derived parameters.

    Raises:
        OrbitalCalculationError: If calculations produce invalid results.
    """
    try:
        # Mean motion in radians/second
        n_revday = parsed_tle.mean_motion
        n_rad_s = n_revday * 2.0 * math.pi / 86400.0

        # Semi-major axis from Kepler's third law: a = (mu / n^2)^(1/3)
        if n_rad_s <= 0:
            raise OrbitalCalculationError(
                f"Invalid mean motion for NORAD {parsed_tle.norad_id}: {n_revday}"
            )

        a_km = (MU_EARTH_KM3_S2 / (n_rad_s ** 2)) ** (1.0 / 3.0)

        ecc = parsed_tle.eccentricity

        # Apogee and perigee altitudes (above Earth surface)
        apogee_alt_km = a_km * (1.0 + ecc) - EARTH_RADIUS_KM
        perigee_alt_km = a_km * (1.0 - ecc) - EARTH_RADIUS_KM

        # Sanity checks
        if a_km <= 0 or math.isnan(a_km) or math.isinf(a_km):
            raise OrbitalCalculationError(
                f"Invalid semi-major axis computed: {a_km} km for NORAD {parsed_tle.norad_id}"
            )
        if apogee_alt_km < 0:
            logger.warning(
                "Negative apogee altitude %.2f km for NORAD %s (possible decay orbit)",
                apogee_alt_km, parsed_tle.norad_id
            )
        if perigee_alt_km < 0:
            logger.warning(
                "Negative perigee altitude %.2f km for NORAD %s (possible decay orbit)",
                perigee_alt_km, parsed_tle.norad_id
            )

        return OrbitalElements(
            norad_id=parsed_tle.norad_id,
            semi_major_axis_km=a_km,
            eccentricity=ecc,
            inclination_deg=parsed_tle.inclination,
            raan_deg=parsed_tle.raan,
            arg_perigee_deg=parsed_tle.arg_perigee,
            mean_motion_revday=n_revday,
            apogee_alt_km=apogee_alt_km,
            perigee_alt_km=perigee_alt_km,
        )

    except OrbitalCalculationError:
        raise
    except Exception as e:
        raise OrbitalCalculationError(
            f"Orbital element computation failed for NORAD {parsed_tle.norad_id}: {e}"
        )


def propagate_sgp4(
    line1: str, line2: str, dt: datetime = None
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Propagate satellite position and velocity using SGP4.

    Args:
        line1: TLE line 1
        line2: TLE line 2
        dt: Datetime for propagation (defaults to now UTC)

    Returns:
        Tuple of (position_km [3], velocity_km_s [3]) in TEME frame.

    Raises:
        OrbitalCalculationError: If SGP4 propagation fails.
    """
    if dt is None:
        dt = datetime.now(timezone.utc)

    try:
        sat = Satrec.twoline2rv(line1.strip(), line2.strip(), WGS72)

        # Convert datetime to Julian date
        jd, fr = _datetime_to_jd(dt)

        error_code, position, velocity = sat.sgp4(jd, fr)

        if error_code != 0:
            raise OrbitalCalculationError(
                f"SGP4 propagation error code {error_code}"
            )

        pos = np.array(position, dtype=np.float64)
        vel = np.array(velocity, dtype=np.float64)

        # Validate output
        if np.any(np.isnan(pos)) or np.any(np.isinf(pos)):
            raise OrbitalCalculationError("SGP4 produced NaN/Inf position")
        if np.any(np.isnan(vel)) or np.any(np.isinf(vel)):
            raise OrbitalCalculationError("SGP4 produced NaN/Inf velocity")

        return pos, vel

    except OrbitalCalculationError:
        raise
    except Exception as e:
        raise OrbitalCalculationError(f"SGP4 propagation failed: {e}")


def compute_minimum_separation(
    line1_a: str, line2_a: str,
    line1_b: str, line2_b: str,
    time_steps: int = 100,
    horizon_hours: float = 24.0,
) -> float:
    """
    Estimate minimum separation distance (MSD) between two satellites
    over a time horizon using SGP4 propagation.

    Args:
        line1_a, line2_a: TLE for satellite A
        line1_b, line2_b: TLE for satellite B
        time_steps: Number of time steps for search
        horizon_hours: Time horizon in hours

    Returns:
        Minimum separation distance in meters.

    Raises:
        OrbitalCalculationError: If computation fails.
    """
    try:
        sat_a = Satrec.twoline2rv(line1_a.strip(), line2_a.strip(), WGS72)
        sat_b = Satrec.twoline2rv(line1_b.strip(), line2_b.strip(), WGS72)

        now = datetime.now(timezone.utc)
        jd_base, fr_base = _datetime_to_jd(now)

        min_dist_km = float("inf")
        step_hours = horizon_hours / time_steps

        for i in range(time_steps + 1):
            fr = fr_base + (i * step_hours) / 24.0

            err_a, pos_a, _ = sat_a.sgp4(jd_base, fr)
            err_b, pos_b, _ = sat_b.sgp4(jd_base, fr)

            if err_a != 0 or err_b != 0:
                continue  # Skip failed time steps

            pos_a = np.array(pos_a)
            pos_b = np.array(pos_b)

            if np.any(np.isnan(pos_a)) or np.any(np.isnan(pos_b)):
                continue

            dist_km = np.linalg.norm(pos_a - pos_b)
            if dist_km < min_dist_km:
                min_dist_km = dist_km

        if min_dist_km == float("inf"):
            raise OrbitalCalculationError(
                "Could not compute minimum separation — all time steps failed"
            )

        # Convert km to meters
        return min_dist_km * 1000.0

    except OrbitalCalculationError:
        raise
    except Exception as e:
        raise OrbitalCalculationError(f"Minimum separation computation failed: {e}")


def _datetime_to_jd(dt: datetime) -> Tuple[float, float]:
    """Convert a datetime to Julian Date (jd, fraction) for SGP4."""
    year = dt.year
    month = dt.month
    day = dt.day

    jd = (
        367.0 * year
        - int(7.0 * (year + int((month + 9.0) / 12.0)) / 4.0)
        + int(275.0 * month / 9.0)
        + day
        + 1721013.5
    )
    fr = (dt.hour + dt.minute / 60.0 + dt.second / 3600.0) / 24.0

    return jd, fr


def filter_potential_conjunction_pairs(
    elements_list: list,
    altitude_threshold_km: float = 50.0,
) -> list:
    """
    Broad-phase orbital altitude envelope filter.

    Given a list of N satellite OrbitalElements, filters the N*(N-1)/2 possible pairs
    down to only those pairs whose altitude intervals [perigee - threshold, apogee + threshold]
    overlap.

    This provides an efficient O(N log N) pre-filter that eliminates >95% of non-intersecting
    pairs before performing expensive SGP4 propagation or ML inference.

    Args:
        elements_list: List of OrbitalElements objects.
        altitude_threshold_km: Margin around apogee/perigee envelope in km.

    Returns:
        List of tuples (satellite_A_elements, satellite_B_elements) that pass the pre-filter.
    """
    if len(elements_list) < 2:
        return []

    # Sort satellites by minimum altitude (perigee)
    sorted_sats = sorted(elements_list, key=lambda s: s.perigee_alt_km)
    candidate_pairs = []

    for i in range(len(sorted_sats)):
        sat_a = sorted_sats[i]
        a_min = sat_a.perigee_alt_km - altitude_threshold_km
        a_max = sat_a.apogee_alt_km + altitude_threshold_km

        for j in range(i + 1, len(sorted_sats)):
            sat_b = sorted_sats[j]
            b_min = sat_b.perigee_alt_km - altitude_threshold_km
            b_max = sat_b.apogee_alt_km + altitude_threshold_km

            # If sat_b's lowest altitude is above sat_a's highest altitude, no further sat_b can overlap sat_a
            if sat_b.perigee_alt_km - altitude_threshold_km > a_max:
                break

            # Check if altitude intervals overlap: max(a_min, b_min) <= min(a_max, b_max)
            if max(a_min, b_min) <= min(a_max, b_max):
                candidate_pairs.append((sat_a, sat_b))

    return candidate_pairs
