from fastapi import APIRouter, HTTPException, Query, Depends
from api.modules.qbo import QBOManager
from fastapi_limiter.depends import RateLimiter
import logging

router = APIRouter()

@router.get("/list_estimates", dependencies=[Depends(RateLimiter(times=5, seconds=60))])
async def list_estimates(from_date: str = Query(..., description="List estimates from this date")):
    """List estimates from a given date."""
    try:
        manager = QBOManager()
        estimates = manager.list_estimates(from_date)
        return {"estimates": estimates}
    except Exception as e:
        logging.error(f"Error listing estimates: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve estimates: {str(e)}"
        ) 