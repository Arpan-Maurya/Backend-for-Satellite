"""
Tests for the risk scoring engine.
"""

import pytest
from app.core.risk_engine import (
    compute_normalized_msd_risk,
    compute_risk_score,
    classify_risk_tier,
    compute_full_risk,
    RiskTier,
    RiskResult,
)


class TestNormalizedMSDRisk:
    def test_zero_distance(self):
        """Zero MSD = maximum risk."""
        assert compute_normalized_msd_risk(0.0, 1000.0) == 1.0

    def test_at_threshold(self):
        """MSD == threshold = zero risk."""
        assert compute_normalized_msd_risk(1000.0, 1000.0) == 0.0

    def test_above_threshold(self):
        """MSD > threshold = zero risk (clamped)."""
        assert compute_normalized_msd_risk(2000.0, 1000.0) == 0.0

    def test_half_threshold(self):
        """MSD = half threshold = 0.5 risk."""
        assert abs(compute_normalized_msd_risk(500.0, 1000.0) - 0.5) < 1e-10

    def test_negative_msd(self):
        """Negative MSD treated as 0 (maximum risk)."""
        assert compute_normalized_msd_risk(-100.0, 1000.0) == 1.0

    def test_invalid_threshold(self):
        with pytest.raises(ValueError):
            compute_normalized_msd_risk(100.0, 0.0)


class TestRiskScore:
    def test_formula_weights(self):
        """60% collision + 40% MSD risk."""
        score = compute_risk_score(1.0, 1.0)
        assert abs(score - 1.0) < 1e-10

    def test_zero_both(self):
        assert compute_risk_score(0.0, 0.0) == 0.0

    def test_only_collision(self):
        assert abs(compute_risk_score(1.0, 0.0) - 0.6) < 1e-10

    def test_only_msd(self):
        assert abs(compute_risk_score(0.0, 1.0) - 0.4) < 1e-10

    def test_clamping_high(self):
        """Values > 1 should be clamped."""
        score = compute_risk_score(1.5, 1.5)
        assert score <= 1.0

    def test_clamping_low(self):
        """Values < 0 should be clamped."""
        score = compute_risk_score(-0.5, -0.5)
        assert score >= 0.0


class TestRiskTierClassification:
    def test_critical(self):
        assert classify_risk_tier(0.9) == RiskTier.CRITICAL

    def test_high(self):
        assert classify_risk_tier(0.7) == RiskTier.HIGH

    def test_medium(self):
        assert classify_risk_tier(0.4) == RiskTier.MEDIUM

    def test_low(self):
        assert classify_risk_tier(0.1) == RiskTier.LOW

    def test_boundary_critical(self):
        assert classify_risk_tier(0.8) == RiskTier.CRITICAL

    def test_boundary_high(self):
        assert classify_risk_tier(0.6) == RiskTier.HIGH

    def test_boundary_medium(self):
        assert classify_risk_tier(0.3) == RiskTier.MEDIUM

    def test_zero(self):
        assert classify_risk_tier(0.0) == RiskTier.LOW


class TestFullRiskComputation:
    def test_returns_risk_result(self):
        result = compute_full_risk(msd_meters=100.0, collision_prob=0.5)
        assert isinstance(result, RiskResult)

    def test_contains_all_fields(self):
        result = compute_full_risk(msd_meters=200.0, collision_prob=0.3)
        assert result.msd_meters == 200.0
        assert result.collision_prob == 0.3
        assert 0 <= result.risk_score <= 1
        assert result.risk_tier in RiskTier

    def test_high_risk_scenario(self):
        """Very close + high probability = CRITICAL."""
        result = compute_full_risk(msd_meters=10.0, collision_prob=0.95)
        assert result.risk_tier == RiskTier.CRITICAL

    def test_low_risk_scenario(self):
        """Far apart + low probability = LOW."""
        result = compute_full_risk(msd_meters=5000.0, collision_prob=0.01)
        assert result.risk_tier == RiskTier.LOW

    def test_model_version_passed(self):
        result = compute_full_risk(msd_meters=100.0, collision_prob=0.5, model_version="v2.0")
        assert result.model_version == "v2.0"
