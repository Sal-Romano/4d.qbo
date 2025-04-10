from fastapi import APIRouter, Depends, HTTPException, status, Request, Header, Query
from fastapi_limiter.depends import RateLimiter
import logging
import os
from api.dependencies import get_api_key
from api.modules.emr import FourDManager

router = APIRouter()

# Make id optional with Query(None) so auth can be checked first
@router.get("/get_quote", dependencies=[Depends(RateLimiter(times=5, seconds=60))], status_code=status.HTTP_200_OK)
async def get_quote(id: str = Query(None), request: Request = None, secret: str = Header(None)):
    """Get quote details by ID from 4D EMR system"""
    
    # Log request info
    logging.info(f"Get quote request received for ID: {id}")
    
    try:
        # Initialize the 4D Manager
        manager = FourDManager()
        
        # Get quote data
        logging.info(f"Requesting quote data for ID: {id}")
        quote_data = manager.get_quote(id)
        
        # Log the response (omit sensitive data)
        logging.info(f"Response received for quote ID: {id}")
        
        # Check for errors
        if "error" in quote_data:
            logging.warning("Quote not found or error occurred")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quote not found"
            )
            
        return quote_data
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
    except HTTPException as http_exc:
        # Re-raise HTTPException to ensure correct status code is returned
        raise http_exc
    except Exception as e:
        logging.error(f"Error getting quote: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        ) 