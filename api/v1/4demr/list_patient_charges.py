from fastapi import APIRouter, Depends, HTTPException, status, Request, Header, Query
from fastapi_limiter.depends import RateLimiter
import logging
from datetime import datetime
from pydantic import BaseModel, Field, validator
from api.main import get_api_key
from api.modules.emr import FourDManager

router = APIRouter()

class DateParams(BaseModel):
    from_date: str = Field(..., description="Starting date in format YYYY-MM-DD")
    to_date: str = Field(..., description="Ending date in format YYYY-MM-DD")
    
    @validator('from_date', 'to_date')
    def validate_date_format(cls, v):
        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError:
            raise ValueError("Incorrect date format, should be YYYY-MM-DD")

@router.get("/list_patient_charges", dependencies=[Depends(RateLimiter(times=5, seconds=60))], status_code=status.HTTP_200_OK)
async def list_patient_charges(
    from_date: str = Query(..., description="Starting date in format YYYY-MM-DD"),
    to_date: str = Query(..., description="Ending date in format YYYY-MM-DD"),
    request: Request = None, 
    secret: str = Header(None)
):
    """Get a list of patient charges between two dates"""
    
    # Log request info
    logging.info(f"List patient charges request received from date: {from_date} to date: {to_date}")
    
    # Validate date formats
    try:
        datetime.strptime(from_date, "%Y-%m-%d")
        datetime.strptime(to_date, "%Y-%m-%d")
    except ValueError:
        logging.error(f"Invalid date format: from_date={from_date}, to_date={to_date}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Required format: YYYY-MM-DD"
        )
    
    try:
        # Initialize the 4D Manager
        manager = FourDManager()
        
        # Get charges list
        logging.info(f"Requesting charges list from date: {from_date} to date: {to_date}")
        charges_data = manager.list_charges(from_date, to_date)
        
        # Log the response
        logging.info(f"Response received for charges list request")
        
        # Check for errors
        if "error" in charges_data:
            logging.error(f"4D manager error: {charges_data['error']}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Charges not found or error: {charges_data['error']}"
            )
            
        return charges_data
    except ImportError as e:
        # Handle missing module
        logging.error(f"4D Manager import error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"4D EMR integration is not properly configured: {str(e)}"
        )
    except ValueError as e:
        # Handle initialization errors (missing credentials)
        logging.error(f"4D Manager initialization error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize 4D connection: {str(e)}"
        )
    except Exception as e:
        # Handle any other errors
        logging.error(f"Error listing charges: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        ) 