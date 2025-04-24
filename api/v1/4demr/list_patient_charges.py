from fastapi import APIRouter, HTTPException, Query
from datetime import datetime
from api.modules.emr import FourDManager

router = APIRouter()

@router.get("/list_patient_charges")
async def list_patient_charges(
    from_date: str = Query(..., description="Starting date in format YYYY-MM-DD"),
    to_date: str = Query(..., description="Ending date in format YYYY-MM-DD")
):
    """
    Get a list of patient charges between two dates from the 4D EMR system.
    """
    # Validate date formats
    try:
        datetime.strptime(from_date, "%Y-%m-%d")
        datetime.strptime(to_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Required format: YYYY-MM-DD")

    try:
        emr = FourDManager()
        result = emr.list_charges(from_date, to_date)
        if "error" in result:
            raise HTTPException(status_code=404, detail=f"Charges not found or error: {result['error']}")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 