from fastapi import APIRouter, Depends, HTTPException, status, Request, Header, Query
from fastapi_limiter.depends import RateLimiter
import logging
import os
from api.dependencies import get_api_key
from api.modules.emr import FourDManager

router = APIRouter()

# Make id optional with Query(None) so auth can be checked first
@router.get("/get_patient", dependencies=[Depends(RateLimiter(times=5, seconds=60))], status_code=status.HTTP_200_OK)
async def get_patient(id: str = Query(None), request: Request = None, secret: str = Header(None)):
    """Get patient details by ID from 4D EMR system"""
    
    # Log request info
    logging.info(f"Get patient request received for ID: {id}")
    
    try:
        # Initialize the 4D Manager
        manager = FourDManager()
        
        # Get patient data
        logging.info(f"Requesting patient data for ID: {id}")
        patient_data = manager.get_patient(id)
        
        # Log the response (omit sensitive data)
        logging.info(f"Response received for patient ID: {id}")
        
        # Check for errors
        if not patient_data or "error" in patient_data:
            logging.warning("Patient not found or error occurred")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found"
            )
            
        return patient_data
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
        logging.error(f"Error getting patient: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        ) 