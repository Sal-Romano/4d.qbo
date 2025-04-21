from fastapi import APIRouter, HTTPException, Query, Depends
from api.modules.qbo import QBOManager
from fastapi_limiter.depends import RateLimiter
import logging
from dateutil import parser
import pytz
from fastapi import status

router = APIRouter()

@router.get("/list_invoices", dependencies=[Depends(RateLimiter(times=30, seconds=60))], status_code=status.HTTP_200_OK)
async def list_invoices(from_date: str = Query(..., description="List invoices from this date")):
    """List invoices from a given date."""
    try:
        manager = QBOManager()
        invoices = manager.list_invoices(from_date)
        # Convert last_updated_time to UTC and rename to last_modified_utc
        for invoice in invoices:
            last_updated = parser.isoparse(invoice['last_updated_time'])
            last_modified_utc = last_updated.astimezone(pytz.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            invoice['last_modified_utc'] = last_modified_utc
            del invoice['last_updated_time']
        return {"invoices": invoices}
    except Exception as e:
        logging.error(f"Error listing invoices: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve invoices: {str(e)}"
        ) 