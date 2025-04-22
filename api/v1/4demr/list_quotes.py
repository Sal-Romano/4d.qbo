from fastapi import APIRouter, Depends, HTTPException, status, Request, Header, Query
from fastapi_limiter.depends import RateLimiter
import logging
from datetime import datetime
from pydantic import BaseModel, Field, validator
from api.main import get_api_key
from api.modules.emr import FourDManager

router = APIRouter()

class DateParams(BaseModel):
    from_date: str = Field(..., description="Starting date in format YYYY-MM-DDTHH:mm:ss (UTC0)")
    
    @validator('from_date')
    def validate_date_format(cls, v):
        try:
            datetime.strptime(v, "%Y-%m-%dT%H:%M:%S")
            return v
        except ValueError:
            raise ValueError("Incorrect date format, should be YYYY-MM-DDTHH:mm:ss")

@router.get("/list_quotes", dependencies=[Depends(RateLimiter(times=5, seconds=60))], status_code=status.HTTP_200_OK)
async def list_quotes(
    from_date: str = Query(..., description="Starting date in format YYYY-MM-DDTHH:mm:ss (UTC0)"),
    request: Request = None, 
    secret: str = Header(None)
):
    """Get a list of quotes from a specific date onwards"""
    
    # Log request info
    logging.info(f"List quotes request received from date: {from_date}")
    
    # Validate date format
    try:
        datetime.strptime(from_date, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        logging.error(f"Invalid date format: {from_date}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Required format: YYYY-MM-DDTHH:mm:ss"
        )
    
    try:
        # Initialize the 4D Manager
        manager = FourDManager()
        
        # Get quotes list
        logging.info(f"Requesting quotes list from date: {from_date}")
        quotes_data = manager.list_quotes(from_date)
        
        # Log the response
        logging.info(f"Response received for quotes list request")
        
        # Check for errors
        if "error" in quotes_data:
            logging.error(f"4D manager error: {quotes_data['error']}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Quotes not found or error: {quotes_data['error']}"
            )
            
        return quotes_data
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
        logging.error(f"Error listing quotes: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        ) 