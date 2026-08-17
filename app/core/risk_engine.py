"""
Risk scoring and tier classification engine.

Implements the combined risk formula:
    risk_score = 0.6 * collision_prob + 0.4 * normalized_msd_risk

Where normalized_msd_risk = max(0, 1 - msd / threshold)
  (closer objects = higher risk)

Tier thresholds (configurable via Settings):
  CRITICAL: >= 0.8
  HIGH:     >= 0.6
  MEDIUM:   >= 0.3
  LOW:      <  0.3
"""

import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class RiskTier(str, Enum):
    """Risk classification tiers."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class RiskResult:
    """Complete risk scoring result."""
    msd_meters: float
    collision_prob: float
    normalized_msd_risk: float
    risk_score: float
    risk_tier: RiskTier
    confidence: float
    model_version: str


def compute_normalized_msd_risk(msd_meters: float, threshold_meters: float = 1000.0) -> float:
    """
    Normalize MSD to a 0-1 risk scale.
    Closer distances (smaller MSD) produce higher risk.

    Formula: max(0, 1 - msd / threshold)

    Args:
        msd_meters: Minimum separation distance in meters.
        threshold_meters: Distance at which MSD risk becomes 0.

    Returns:
        Float in [0, 1]. 0 = no MSD risk, 1 = maximum MSD risk.
    """
    if threshold_meters <= 0:
        raise ValueError("MSD threshold must be positive")
    if msd_meters < 0:
        msd_meters = 0.0  # Treat negative MSD as zero (maximum risk)
    return max(0.0, 1.0 - msd_meters / threshold_meters)


def compute_risk_score(collision_prob: float, normalized_msd_risk: float) -> float:
    """
    Compute combined risk score from 60% collision probability + 40% MSD risk.

    Args:
        collision_prob: Model-predicted collision probability [0, 1].
        normalized_msd_risk: Normalized MSD risk [0, 1].

    Returns:
        Combined risk score in [0, 1].
    """
    # Clamp inputs to valid range
    collision_prob = max(0.0, min(1.0, collision_prob))
    normalized_msd_risk = max(0.0, min(1.0, normalized_msd_risk))

    return 0.6 * collision_prob + 0.4 * normalized_msd_risk


def classify_risk_tier(
    risk_score: float,
    critical_threshold: float = 0.8,
    high_threshold: float = 0.6,
    medium_threshold: float = 0.3,
) -> RiskTier:
    """
    Classify risk score into a tier.

    Args:
        risk_score: Combined score in [0, 1].
        critical_threshold: Score >= this = CRITICAL
        high_threshold: Score >= this = HIGH
        medium_threshold: Score >= this = MEDIUM

    Returns:
        RiskTier enum value.
    """
    if risk_score >= critical_threshold:
        return RiskTier.CRITICAL
    elif risk_score >= high_threshold:
        return RiskTier.HIGH
    elif risk_score >= medium_threshold:
        return RiskTier.MEDIUM
    else:
        return RiskTier.LOW


def compute_full_risk(
    msd_meters: float,
    collision_prob: float,
    model_version: str = "unknown",
    confidence: float = 0.0,
    msd_threshold: float = 1000.0,
    critical_threshold: float = 0.8,
    high_threshold: float = 0.6,
    medium_threshold: float = 0.3,
) -> RiskResult:
    """
    End-to-end risk computation.

    Args:
        msd_meters: Predicted minimum separation distance in meters.
        collision_prob: Predicted collision probability [0, 1].
        model_version: Version string of the model used.
        confidence: Prediction confidence score.
        msd_threshold: MSD normalization threshold in meters.
        critical_threshold: Score >= this = CRITICAL.
        high_threshold: Score >= this = HIGH.
        medium_threshold: Score >= this = MEDIUM.

    Returns:
        RiskResult with all computed values.
    """
    normalized_msd = compute_normalized_msd_risk(msd_meters, msd_threshold)
    score = compute_risk_score(collision_prob, normalized_msd)
    tier = classify_risk_tier(score, critical_threshold, high_threshold, medium_threshold)

    result = RiskResult(
        msd_meters=msd_meters,
        collision_prob=collision_prob,
        normalized_msd_risk=normalized_msd,
        risk_score=round(score, 6),
        risk_tier=tier,
        confidence=confidence,
        model_version=model_version,
    )

    logger.info(
        "Risk computed: MSD=%.1fm, P=%.4f, norm_MSD=%.4f, score=%.4f, tier=%s",
        msd_meters, collision_prob, normalized_msd, score, tier.value,
    )

    return result
