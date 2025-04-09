from fastapi import FastAPI, HTTPException, Header, Depends, status, Request
from fastapi.security import APIKeyHeader
import os
from dotenv import load_dotenv
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
import logging
import aioredis
from contextlib import asynccontextmanager

# Load environment variables
load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Redis for rate limiting
    redis = await aioredis.from_url("redis://localhost")
    await FastAPILimiter.init(redis)
    yield

app = FastAPI(lifespan=lifespan)

API_KEY = os.getenv("API_KEY")
API_KEY_NAME = "secret" # Name of the header to check
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

API_PORT = int(os.getenv("API_PORT", 9742))  # Default to 9742 if not set

# Initialize logging
LOG_DIR = os.getenv('LOG_DIR', './logs')
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

logging.basicConfig(
    filename=os.path.join(LOG_DIR, 'api.log'),
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def get_api_key(key: str = Depends(api_key_header)):
    if key == API_KEY:
        return key
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Bearer"}, # Optional, typically used for Bearer tokens but sets the context
        )

@app.api_route("/status", methods=["GET", "HEAD"], status_code=status.HTTP_200_OK)
# For HEAD requests, FastAPI/Starlette automatically returns only headers
def read_status():
    return {"status": "API is online"}

@app.get("/test", dependencies=[Depends(get_api_key), Depends(RateLimiter(times=5, seconds=60))], status_code=status.HTTP_200_OK)
# If execution reaches here, the API key is valid
def read_test():
    return {"message": "Authorized"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=API_PORT) 