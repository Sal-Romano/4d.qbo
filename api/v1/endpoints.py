from fastapi import APIRouter, Depends, status
from fastapi_limiter.depends import RateLimiter
from api.dependencies import get_api_key

router = APIRouter()

@router.api_route("/status", methods=["GET", "HEAD"], status_code=status.HTTP_200_OK)
# For HEAD requests, FastAPI/Starlette automatically returns only headers
def read_status():
    return {"status": "API is online"}

@router.get("/test", dependencies=[Depends(get_api_key), Depends(RateLimiter(times=5, seconds=60))], status_code=status.HTTP_200_OK)
# If execution reaches here, the API key is valid
def read_test():
    return {"message": "Authorized"} 