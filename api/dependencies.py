from fastapi import HTTPException, Depends, status
from fastapi.security import APIKeyHeader
import os

API_KEY = os.getenv("API_KEY")
API_KEY_NAME = "secret"  # Name of the header to check
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_api_key(key: str = Depends(api_key_header)):
    if key == API_KEY:
        return key
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Bearer"},  # Optional, typically used for Bearer tokens but sets the context
        ) 