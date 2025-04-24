from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi_limiter.depends import RateLimiter
from datetime import datetime
from api.modules.emr import FourDManager

router = APIRouter()

@router.get("/list_quotes", dependencies=[Depends(RateLimiter(times=5, seconds=60))], status_code=status.HTTP_200_OK)
async def list_quotes(
    from_date: str = Query(..., description="Starting date in format YYYY-MM-DDTHH:mm:ss (UTC0)")
):
    """
    Get a list of quotes from a specific date onwards from the 4D EMR system.
    """
    # Validate date format
    try:
        datetime.strptime(from_date, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Required format: YYYY-MM-DDTHH:mm:ss"
        )

    try:
        emr = FourDManager()
        result = emr.list_quotes(from_date)
        if "error" in result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Quotes not found or error: {result['error']}"
            )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)) 