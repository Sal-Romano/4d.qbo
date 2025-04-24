from fastapi import APIRouter, HTTPException, Query
from api.modules.emr import FourDManager

router = APIRouter()

@router.get("/get_quote")
async def get_quote(id: str = Query(..., description="The ID of the quote to retrieve")):
    """
    Get a specific quote by ID from the 4D EMR system.
    """
    try:
        emr = FourDManager()
        result = emr.get_quote(id)
        if "error" in result:
            # If it's a 404 from the 4D EMR API, return a proper 404 response
            if isinstance(result["error"], str) and "404" in result["error"]:
                raise HTTPException(status_code=404, detail="Quote not found")
            raise HTTPException(status_code=500, detail=result["error"])
        return result
    except Exception as e:
        error_msg = str(e)
        if "404" in error_msg:
            raise HTTPException(status_code=404, detail="Quote not found")
        raise HTTPException(status_code=500, detail=error_msg) 