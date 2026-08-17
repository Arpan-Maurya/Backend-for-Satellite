"""
Risk assessment API routes.
"""

from fastapi import APIRouter, Query, HTTPException, Request
from app.core.limiter import limiter
from app.schemas.risk import (
    RiskAssessmentRequest,
    RiskAssessmentResponse,
    TopConjunctionsResponse,
)
from app.services.assessment_service import run_risk_assessment
from app.db import assessment_repo
from app.core.exceptions import (
    TLEValidationError,
    OrbitalCalculationError,
    FeatureEngineeringError,
    ModelNotLoadedError,
    ModelPredictionError,
    AssessmentNotFoundError,
    DatabaseError,
)

import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/risk", tags=["Risk Assessment"])


@router.post(
    "/assess",
    response_model=RiskAssessmentResponse,
    summary="Assess collision risk between two satellites",
    description=(
        "Accepts TLE data for two satellites and runs the full pipeline: "
        "TLE parsing → orbital element extraction → 8-feature engineering → "
        "XGBoost inference → risk scoring → persistence. "
        "Returns MSD, collision probability, combined risk score, and risk tier."
    ),
    responses={
        400: {"description": "Invalid TLE data"},
        503: {"description": "ML models or database unavailable"},
    },
)
@limiter.limit("60/minute")
async def assess_risk(request: Request, body: RiskAssessmentRequest) -> RiskAssessmentResponse:
    try:
        result = run_risk_assessment(
            line1_a=body.satellite_1.line1,
            line2_a=body.satellite_1.line2,
            line1_b=body.satellite_2.line1,
            line2_b=body.satellite_2.line2,
            name_a=body.satellite_1.name,
            name_b=body.satellite_2.name,
        )

        if result.get("risk_tier") in ("HIGH", "CRITICAL"):
            try:
                from app.api.websocket import broadcast_risk_alert
                await broadcast_risk_alert(result)
            except Exception as ws_err:
                logger.debug("WebSocket broadcast skipped/failed: %s", ws_err)

        return RiskAssessmentResponse(**result)

    except TLEValidationError as e:
        raise HTTPException(status_code=400, detail=e.message)
    except OrbitalCalculationError as e:
        raise HTTPException(status_code=422, detail=e.message)
    except FeatureEngineeringError as e:
        raise HTTPException(status_code=422, detail=e.message)
    except ModelNotLoadedError as e:
        raise HTTPException(status_code=503, detail=e.message)
    except ModelPredictionError as e:
        raise HTTPException(status_code=500, detail="Risk prediction failed")
    except Exception as e:
        logger.exception("Unexpected error during risk assessment")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/top-conjunctions",
    response_model=TopConjunctionsResponse,
    summary="Get highest-risk conjunction assessments",
    description="Returns stored assessments ordered by risk score (highest first).",
)
async def top_conjunctions(
    limit: int = Query(default=100, ge=1, le=500, description="Max results"),
) -> TopConjunctionsResponse:
    try:
        records = assessment_repo.get_top_conjunctions(limit=limit)
        items = []
        for r in records:
            items.append(RiskAssessmentResponse(
                assessment_id=r.get("id"),
                sat1_norad_id=r.get("sat1_norad_id", ""),
                sat2_norad_id=r.get("sat2_norad_id", ""),
                msd_predicted_meters=r.get("msd_predicted", 0),
                collision_probability=r.get("collision_prob", 0),
                normalized_msd_risk=0,  # Not stored, recompute if needed
                risk_score=r.get("risk_score", 0),
                risk_tier=r.get("risk_tier", "LOW"),
                confidence=r.get("confidence", 0),
                model_version=r.get("model_version", "unknown"),
                is_mock=False,
                timestamp=r.get("created_at", ""),
            ))
        return TopConjunctionsResponse(
            conjunctions=items,
            count=len(items),
            limit=limit,
        )
    except DatabaseError:
        raise HTTPException(status_code=503, detail="Database unavailable")


@router.get(
    "/{assessment_id}",
    response_model=RiskAssessmentResponse,
    summary="Get a specific risk assessment",
    description="Returns a single conjunction assessment by its UUID.",
    responses={404: {"description": "Assessment not found"}},
)
async def get_assessment(assessment_id: str) -> RiskAssessmentResponse:
    try:
        r = assessment_repo.get_assessment_by_id(assessment_id)
        return RiskAssessmentResponse(
            assessment_id=r.get("id"),
            sat1_norad_id=r.get("sat1_norad_id", ""),
            sat2_norad_id=r.get("sat2_norad_id", ""),
            msd_predicted_meters=r.get("msd_predicted", 0),
            collision_probability=r.get("collision_prob", 0),
            normalized_msd_risk=0,
            risk_score=r.get("risk_score", 0),
            risk_tier=r.get("risk_tier", "LOW"),
            confidence=r.get("confidence", 0),
            model_version=r.get("model_version", "unknown"),
            is_mock=False,
            timestamp=r.get("created_at", ""),
        )
    except AssessmentNotFoundError:
        raise HTTPException(status_code=404, detail=f"Assessment {assessment_id} not found")
    except DatabaseError:
        raise HTTPException(status_code=503, detail="Database unavailable")
