from fastapi import APIRouter, HTTPException, Query, Depends
from api.modules.qbo import QBOManager
from fastapi_limiter.depends import RateLimiter
import logging

router = APIRouter()

@router.get("/get_customer", dependencies=[Depends(RateLimiter(times=5, seconds=60))])
async def get_customer(display_name: str = Query(..., description="The display name of the customer to retrieve")):
    """Get a customer by DisplayName from QuickBooks Online."""
    try:
        manager = QBOManager()
        customer = manager.get_customer_by_display_name(display_name)
        if not customer:
            logging.warning("Customer not found")
            raise HTTPException(status_code=404, detail="Customer not found")
        return customer
    except HTTPException as http_exc:
        # Re-raise HTTPException to ensure correct status code is returned
        raise http_exc
    except Exception as e:
        logging.error(f"Error retrieving customer: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error") 