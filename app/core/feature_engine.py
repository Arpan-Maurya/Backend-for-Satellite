"""
8-Feature engineering for satellite collision risk assessment.

Computes pairwise orbital features from two satellites' orbital elements.
Feature order is deterministic and MUST match model training exactly.

Features (in order):
  0. inc_diff       - absolute inclination difference (degrees)
  1. raan_diff      - RAAN difference (degrees, wrapped to [0, 180])
  2. ecc_diff       - absolute eccentricity difference
  3. sma_diff       - semi-major axis difference (km)
  4. argp_diff      - argument of perigee difference (degrees, wrapped to [0, 180])
  5. mean_motion_diff - absolute mean motion difference (rev/day)
  6. apogee_diff    - absolute apogee altitude difference (km)
  7. perigee_diff   - absolute perigee altitude difference (km)
"""

import logging
import math
from typing import List

import numpy as np

from app.core.exceptions import FeatureEngineeringError
from app.core.orbital_calc import OrbitalElements

logger = logging.getLogger(__name__)

# Canonical feature names in exact model-training order
FEATURE_NAMES: List[str] = [
    "inc_diff",
    "raan_diff",
    "ecc_diff",
    "sma_diff",
    "argp_diff",
    "mean_motion_diff",
    "apogee_diff",
    "perigee_diff",
]

EXPECTED_FEATURE_COUNT = 8


def _angular_difference(a_deg: float, b_deg: float) -> float:
    """
    Compute the minimum angular difference between two angles in degrees.
    Result is in [0, 180].
    """
    diff = abs(a_deg - b_deg) % 360.0
    return diff if diff <= 180.0 else 360.0 - diff


def compute_features(
    elem_a: OrbitalElements,
    elem_b: OrbitalElements,
) -> np.ndarray:
    """
    Compute the 8 pairwise orbital features for a satellite pair.

    Args:
        elem_a: Orbital elements for satellite A.
        elem_b: Orbital elements for satellite B.

    Returns:
        numpy array of shape (8,) with features in canonical order.

    Raises:
        FeatureEngineeringError: If any feature is NaN, Inf, or computation fails.
    """
    try:
        features = np.array([
            # 0. inc_diff: absolute inclination difference
            abs(elem_a.inclination_deg - elem_b.inclination_deg),

            # 1. raan_diff: RAAN difference (angular, wrapped)
            _angular_difference(elem_a.raan_deg, elem_b.raan_deg),

            # 2. ecc_diff: absolute eccentricity difference
            abs(elem_a.eccentricity - elem_b.eccentricity),

            # 3. sma_diff: semi-major axis difference (km)
            abs(elem_a.semi_major_axis_km - elem_b.semi_major_axis_km),

            # 4. argp_diff: argument of perigee difference (angular, wrapped)
            _angular_difference(elem_a.arg_perigee_deg, elem_b.arg_perigee_deg),

            # 5. mean_motion_diff: absolute mean motion difference
            abs(elem_a.mean_motion_revday - elem_b.mean_motion_revday),

            # 6. apogee_diff: absolute apogee altitude difference (km)
            abs(elem_a.apogee_alt_km - elem_b.apogee_alt_km),

            # 7. perigee_diff: absolute perigee altitude difference (km)
            abs(elem_a.perigee_alt_km - elem_b.perigee_alt_km),
        ], dtype=np.float64)

    except Exception as e:
        raise FeatureEngineeringError(f"Feature computation failed: {e}")

    # Validate output
    _validate_features(features, elem_a.norad_id, elem_b.norad_id)

    logger.debug(
        "Features for %s vs %s: %s",
        elem_a.norad_id, elem_b.norad_id,
        dict(zip(FEATURE_NAMES, features))
    )

    return features


def _validate_features(
    features: np.ndarray,
    norad_a: str,
    norad_b: str,
) -> None:
    """
    Validate computed features for NaN, Inf, and correct count.

    Raises:
        FeatureEngineeringError: If validation fails.
    """
    if features.shape[0] != EXPECTED_FEATURE_COUNT:
        raise FeatureEngineeringError(
            f"Expected {EXPECTED_FEATURE_COUNT} features, got {features.shape[0]} "
            f"for pair {norad_a} vs {norad_b}"
        )

    if np.any(np.isnan(features)):
        nan_indices = np.where(np.isnan(features))[0]
        nan_names = [FEATURE_NAMES[i] for i in nan_indices]
        raise FeatureEngineeringError(
            f"NaN features for {norad_a} vs {norad_b}: {nan_names}"
        )

    if np.any(np.isinf(features)):
        inf_indices = np.where(np.isinf(features))[0]
        inf_names = [FEATURE_NAMES[i] for i in inf_indices]
        raise FeatureEngineeringError(
            f"Infinite features for {norad_a} vs {norad_b}: {inf_names}"
        )

    # Range checks for physically meaningful values
    if features[0] > 180.0:  # inc_diff
        raise FeatureEngineeringError(
            f"Inclination difference > 180° ({features[0]:.2f}) for {norad_a} vs {norad_b}"
        )
    if features[1] > 180.0:  # raan_diff
        raise FeatureEngineeringError(
            f"RAAN difference > 180° ({features[1]:.2f}) for {norad_a} vs {norad_b}"
        )


def features_to_dict(features: np.ndarray) -> dict:
    """Convert feature array to named dictionary."""
    if features.shape[0] != EXPECTED_FEATURE_COUNT:
        raise FeatureEngineeringError(
            f"Expected {EXPECTED_FEATURE_COUNT} features, got {features.shape[0]}"
        )
    return dict(zip(FEATURE_NAMES, features.tolist()))
