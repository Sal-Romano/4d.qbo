from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
import os
from dotenv import load_dotenv
from fastapi_limiter import FastAPILimiter
import logging
import aioredis
from contextlib import asynccontextmanager
import sys
import importlib.util

# Add the current directory to path to ensure imports work regardless of how the script is run
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Use absolute import instead of relative import
from api.router_manager import discover_routers

# Load environment variables
load_dotenv()

# Initialize logging
LOG_DIR = os.getenv('LOG_DIR', './logs')
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

logging.basicConfig(
    filename=os.path.join(LOG_DIR, 'api.log'),
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Fixed port configuration from .env file
API_PORT = int(os.getenv("API_PORT", 9742))  # Default to 9742 if not set
API_PREFIX = os.getenv("API_PREFIX", "/api.v1")  # Default prefix for all endpoints
API_KEY = os.getenv("API_KEY")  # API Key for authentication

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Redis for rate limiting
    redis = await aioredis.from_url("redis://localhost")
    await FastAPILimiter.init(redis)
    yield

app = FastAPI(lifespan=lifespan)

# Add middleware to handle unauthorized requests consistently
@app.middleware("http")
async def check_auth_middleware(request: Request, call_next):
    # Allow status endpoint without auth
    if request.url.path.endswith("/status"):
        return await call_next(request)
    
    # Check for auth header for all other endpoints
    auth_header = request.headers.get("secret")
    
    # If no auth header or wrong key, return 401 Unauthorized
    if not auth_header or auth_header != API_KEY:
        logging.warning(f"Unauthorized access attempt: {request.url.path}")
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Unauthorized"}
        )
    
    # Continue with the request if authorized
    return await call_next(request)

# Discover and register all routers
discover_routers(app, API_PREFIX)

if __name__ == "__main__":
    import uvicorn
    logging.info(f"Starting server on fixed port {API_PORT}")
    # Start with auto-reload enabled
    uvicorn.run(
        "api.main:app", 
        host="0.0.0.0", 
        port=API_PORT,
        reload=True,  # Enable auto-reload
        reload_dirs=["api"],  # Watch only the api directory
    ) 