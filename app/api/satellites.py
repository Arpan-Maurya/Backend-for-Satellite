"""
Satellite API routes.
"""

from fastapi import APIRouter, Query, HTTPException
from app.schemas.satellite import SatelliteResponse, SatelliteListResponse
from app.core.exceptions import SatelliteNotFoundError, DatabaseError
from app.db import satellite_repo

import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/satellites", tags=["Satellites"])


@router.get(
    "",
    response_model=SatelliteListResponse,
    summary="List satellites",
    description="Returns paginated satellite records stored in the database.",
)
async def list_satellites(
    limit: int = Query(default=100, ge=1, le=1000, description="Max results"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
) -> SatelliteListResponse:
    try:
        satellites = satellite_repo.list_satellites(limit=limit, offset=offset)
        total = satellite_repo.count_satellites()
        return SatelliteListResponse(
            satellites=[SatelliteResponse(**s) for s in satellites],
            total=total,
            limit=limit,
            offset=offset,
        )
    except DatabaseError:
        raise HTTPException(status_code=503, detail="Database unavailable")


@router.get(
    "/{norad_id}",
    response_model=SatelliteResponse,
    summary="Get satellite by NORAD ID",
    description="Returns a single satellite record by its NORAD catalog ID.",
    responses={404: {"description": "Satellite not found"}},
)
async def get_satellite(norad_id: str) -> SatelliteResponse:
    try:
        data = satellite_repo.get_satellite_by_norad_id(norad_id)
        return SatelliteResponse(**data)
    except SatelliteNotFoundError:
        raise HTTPException(status_code=404, detail=f"Satellite {norad_id} not found")
    except DatabaseError:
        raise HTTPException(status_code=503, detail="Database unavailable")
