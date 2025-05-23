from fastapi import APIRouter, HTTPException, Request, Depends
from api.modules.qbo import QBOManager
from fastapi_limiter.depends import RateLimiter
import logging
from fastapi import status

router = APIRouter()

@router.post("/batch", dependencies=[Depends(RateLimiter(times=30, seconds=60))], status_code=status.HTTP_200_OK)
async def process_batch(request: Request):
    """Process a batch of requests to the QuickBooks Online API."""
    try:
        batch_request = await request.json()
        batch_items = batch_request.get("BatchItemRequest", [])
        if len(batch_items) > 30:
            raise HTTPException(status_code=400, detail="Batch request exceeds 30 items limit.")

        manager = QBOManager()
        # Just pass through the raw QuickBooks response
        return manager.send_batch_request(batch_request)
        
    except Exception as e:
        logging.error(f"Error processing batch request: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process batch request.") 