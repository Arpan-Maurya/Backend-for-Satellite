"""
Tests for the 8-feature engineering pipeline.
"""

import pytest
import numpy as np
from app.core.feature_engine import (
    compute_features,
    _angular_difference,
    _validate_features,
    features_to_dict,
    FEATURE_NAMES,
    EXPECTED_FEATURE_COUNT,
)
from app.core.orbital_calc import OrbitalElements
from app.core.exceptions import FeatureEngineeringError


@pytest.fixture
def elements_a():
    return OrbitalElements(
        norad_id="25544",
        semi_major_axis_km=6793.0,
        eccentricity=0.0006703,
        inclination_deg=51.64,
        raan_deg=208.9163,
        arg_perigee_deg=358.1484,
        mean_motion_revday=15.502,
        apogee_alt_km=420.0,
        perigee_alt_km=415.0,
    )


@pytest.fixture
def elements_b():
    return OrbitalElements(
        norad_id="48274",
        semi_major_axis_km=6900.0,
        eccentricity=0.001,
        inclination_deg=53.05,
        raan_deg=120.0,
        arg_perigee_deg=90.0,
        mean_motion_revday=15.064,
        apogee_alt_km=530.0,
        perigee_alt_km=520.0,
    )


class TestAngularDifference:
    def test_same_angle(self):
        assert _angular_difference(45.0, 45.0) == 0.0

    def test_simple_diff(self):
        assert abs(_angular_difference(10.0, 30.0) - 20.0) < 1e-10

    def test_wraparound(self):
        """350° and 10° should be 20° apart."""
        assert abs(_angular_difference(350.0, 10.0) - 20.0) < 1e-10

    def test_max_difference(self):
        """0° and 180° should be 180° apart."""
        assert abs(_angular_difference(0.0, 180.0) - 180.0) < 1e-10


class TestFeatureComputation:
    def test_feature_count(self, elements_a, elements_b):
        features = compute_features(elements_a, elements_b)
        assert features.shape == (EXPECTED_FEATURE_COUNT,)

    def test_feature_dtype(self, elements_a, elements_b):
        features = compute_features(elements_a, elements_b)
        assert features.dtype == np.float64

    def test_no_nan(self, elements_a, elements_b):
        features = compute_features(elements_a, elements_b)
        assert not np.any(np.isnan(features))

    def test_no_inf(self, elements_a, elements_b):
        features = compute_features(elements_a, elements_b)
        assert not np.any(np.isinf(features))

    def test_all_non_negative(self, elements_a, elements_b):
        """All difference features should be >= 0."""
        features = compute_features(elements_a, elements_b)
        assert np.all(features >= 0)

    def test_inc_diff(self, elements_a, elements_b):
        features = compute_features(elements_a, elements_b)
        expected = abs(51.64 - 53.05)
        assert abs(features[0] - expected) < 0.01

    def test_ecc_diff(self, elements_a, elements_b):
        features = compute_features(elements_a, elements_b)
        expected = abs(0.0006703 - 0.001)
        assert abs(features[2] - expected) < 1e-6

    def test_symmetric(self, elements_a, elements_b):
        """Features should be same regardless of satellite order."""
        features_ab = compute_features(elements_a, elements_b)
        features_ba = compute_features(elements_b, elements_a)
        np.testing.assert_array_almost_equal(features_ab, features_ba)


class TestFeatureValidation:
    def test_valid_features(self, elements_a, elements_b):
        features = compute_features(elements_a, elements_b)
        _validate_features(features, "A", "B")  # Should not raise

    def test_nan_rejection(self):
        features = np.array([1, 2, np.nan, 4, 5, 6, 7, 8])
        with pytest.raises(FeatureEngineeringError, match="NaN"):
            _validate_features(features, "A", "B")

    def test_inf_rejection(self):
        features = np.array([1, 2, 3, np.inf, 5, 6, 7, 8])
        with pytest.raises(FeatureEngineeringError, match="Infinite"):
            _validate_features(features, "A", "B")

    def test_wrong_count(self):
        features = np.array([1, 2, 3, 4, 5])
        with pytest.raises(FeatureEngineeringError, match="Expected 8"):
            _validate_features(features, "A", "B")


class TestFeatureNames:
    def test_feature_name_count(self):
        assert len(FEATURE_NAMES) == EXPECTED_FEATURE_COUNT

    def test_features_to_dict(self, elements_a, elements_b):
        features = compute_features(elements_a, elements_b)
        d = features_to_dict(features)
        assert len(d) == 8
        assert "inc_diff" in d
        assert "raan_diff" in d
        assert "perigee_diff" in d
