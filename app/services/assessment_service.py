"""
Assessment service — orchestrates the full risk assessment pipeline.

Pipeline: TLE → parse → orbital elements → features → ML inference → risk scoring → persist → respond

This is the single point of orchestration. API routes delegate here.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

import numpy as np

from app.config import get_settings
from app.core.tle_parser import parse_tle, ParsedTLE
from app.core.orbital_calc import compute_orbital_elements, OrbitalElements
from app.core.feature_engine import compute_features
from app.core.risk_engine import compute_full_risk, RiskResult, RiskTier
from app.ml.model_manager import model_manager
from app.db import satellite_repo, assessment_repo, alert_repo
from app.core.exceptions import (
    TLEValidationError,
    OrbitalCalculationError,
    FeatureEngineeringError,
    ModelNotLoadedError,
    ModelPredictionError,
    DatabaseError,
)

logger = logging.getLogger(__name__)


def run_risk_assessment(
    line1_a: str,
    line2_a: str,
    line1_b: str,
    line2_b: str,
    name_a: Optional[str] = None,
    name_b: Optional[str] = None,
) -> dict:
    """
    Execute the full collision risk assessment pipeline.

    Args:
        line1_a, line2_a: TLE for satellite A
        line1_b, line2_b: TLE for satellite B
        name_a: Optional name for satellite A
        name_b: Optional name for satellite B

    Returns:
        Dict matching RiskAssessmentResponse schema.

    Raises:
        TLEValidationError, OrbitalCalculationError, FeatureEngineeringError,
        ModelNotLoadedError, ModelPredictionError
    """
    settings = get_settings()

    # Step 1: Parse and validate TLE data
    logger.info("Step 1/6: Parsing TLE data")
    parsed_a = parse_tle(line1_a, line2_a, name=name_a)
    parsed_b = parse_tle(line1_b, line2_b, name=name_b)

    # Step 2: Compute orbital elements
    logger.info("Step 2/6: Computing orbital elements")
    elements_a = compute_orbital_elements(parsed_a)
    elements_b = compute_orbital_elements(parsed_b)

    # Step 3: Engineer 8 features
    logger.info("Step 3/6: Engineering features")
    features = compute_features(elements_a, elements_b)

    # Step 4: ML inference
    logger.info("Step 4/6: Running ML inference")
    msd_predicted, collision_prob, confidence = model_manager.predict(features)

    # Step 5: Risk scoring
    logger.info("Step 5/6: Computing risk score")
    risk_result = compute_full_risk(
        msd_meters=msd_predicted,
        collision_prob=collision_prob,
        model_version=model_manager.model_version,
        confidence=confidence,
        msd_threshold=settings.risk_msd_threshold,
        critical_threshold=settings.risk_critical,
        high_threshold=settings.risk_high,
        medium_threshold=settings.risk_medium,
    )

    # Step 6: Persist to database
    logger.info("Step 6/6: Persisting results")
    assessment_id = None
    try:
        # Upsert satellites
        satellite_repo.upsert_satellite(
            norad_id=parsed_a.norad_id,
            name=parsed_a.name,
            tle_line1=parsed_a.line1,
            tle_line2=parsed_a.line2,
        )
        satellite_repo.upsert_satellite(
            norad_id=parsed_b.norad_id,
            name=parsed_b.name,
            tle_line1=parsed_b.line1,
            tle_line2=parsed_b.line2,
        )

        # Create assessment record
        record = assessment_repo.create_assessment(
            sat1_norad_id=parsed_a.norad_id,
            sat2_norad_id=parsed_b.norad_id,
            msd_predicted=risk_result.msd_meters,
            collision_prob=risk_result.collision_prob,
            risk_score=risk_result.risk_score,
            risk_tier=risk_result.risk_tier.value,
            confidence=risk_result.confidence,
            model_version=risk_result.model_version,
        )
        assessment_id = record.get("id")

        # Create alert for HIGH/CRITICAL risks
        if risk_result.risk_tier in (RiskTier.HIGH, RiskTier.CRITICAL):
            alert_repo.create_alert(
                sat1_norad_id=parsed_a.norad_id,
                sat2_norad_id=parsed_b.norad_id,
                risk_tier=risk_result.risk_tier.value,
                message=(
                    f"Collision risk {risk_result.risk_tier.value}: "
                    f"{parsed_a.name or parsed_a.norad_id} vs "
                    f"{parsed_b.name or parsed_b.norad_id} — "
                    f"score={risk_result.risk_score:.4f}, "
                    f"MSD={risk_result.msd_meters:.1f}m"
                ),
            )

    except DatabaseError as e:
        logger.warning("Database persistence failed (non-fatal): %s", e)
        # Persist failure is non-fatal — still return the computed result

    now = datetime.now(timezone.utc).isoformat()

    return {
        "assessment_id": assessment_id,
        "sat1_norad_id": parsed_a.norad_id,
        "sat2_norad_id": parsed_b.norad_id,
        "sat1_name": parsed_a.name,
        "sat2_name": parsed_b.name,
        "msd_predicted_meters": round(risk_result.msd_meters, 2),
        "collision_probability": round(risk_result.collision_prob, 6),
        "normalized_msd_risk": round(risk_result.normalized_msd_risk, 6),
        "risk_score": round(risk_result.risk_score, 6),
        "risk_tier": risk_result.risk_tier.value,
        "confidence": round(risk_result.confidence, 4),
        "model_version": risk_result.model_version,
        "is_mock": model_manager.is_mock,
        "timestamp": now,
    }
