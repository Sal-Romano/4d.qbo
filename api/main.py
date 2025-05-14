from fastapi import FastAPI, Request, status, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
import os
from dotenv import load_dotenv
from fastapi_limiter import FastAPILimiter
import logging
import aioredis
from contextlib import asynccontextmanager
import sys
import importlib
import pkgutil
import inspect
from fastapi import APIRouter

# Add the current directory to path to ensure imports work regardless of how the script is run
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Load environment variables
load_dotenv()

# Initialize logging
LOG_DIR = os.getenv('LOG_DIR', './logs')
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# Configure logging with specific level for watchfiles
logging.basicConfig(
    filename=os.path.join(LOG_DIR, 'api.log'),
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Suppress watchfiles INFO messages
logging.getLogger('watchfiles.main').setLevel(logging.WARNING)

# Fixed port configuration from .env file
API_PORT = int(os.getenv("API_PORT", 9742))  # Default to 9742 if not set
API_PREFIX = os.getenv("API_PREFIX", "/api.v1")  # Default prefix for all endpoints
API_KEY = os.getenv("API_KEY")  # API Key for authentication

# API Key authentication setup
API_KEY_NAME = "secret"  # Name of the header to check
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_api_key(key: str = Depends(api_key_header)):
    """Dependency function to check API key."""
    if key == API_KEY:
        return key
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized",
        headers={"WWW-Authenticate": "Bearer"},
    )

def discover_routers(app: FastAPI, api_prefix: str = "/api.v1", package_name: str = "api.v1"):
    """
    Discovers and registers all routers in the specified package.
    """
    print(f"Discovering routers in {package_name}...")
    logging.info(f"Discovering routers in {package_name}...")
    
    # Import the package (api.v1)
    package = importlib.import_module(package_name)
    package_path = os.path.dirname(package.__file__)
    
    # Register main endpoints.py in v1 package if it exists
    if hasattr(package, "endpoints") and hasattr(package.endpoints, "router"):
        print(f"Mounting main endpoints router from {package_name}.endpoints at {api_prefix}")
        logging.info(f"Mounting main endpoints router from {package_name}.endpoints")
        app.include_router(package.endpoints.router, prefix=api_prefix)
    
    # Recursively discover routers in all subpackages
    discovered = pkgutil.walk_packages(path=[package_path], prefix=f"{package_name}.")
    
    for _, module_name, is_pkg in discovered:
        if not is_pkg:  # If it's a module (not a package)
            try:
                module = importlib.import_module(module_name)
                
                # Look for router objects in the module
                for attr_name, attr_value in inspect.getmembers(module):
                    if isinstance(attr_value, APIRouter):
                        router_path = module_name.replace(package_name, "")
                        if router_path.endswith(".py"):
                            router_path = router_path[:-3]
                        
                        # Get just the directory part for the router prefix
                        last_dot = router_path.rfind('.')
                        if last_dot != -1:
                            dir_path = router_path[:last_dot]
                            dir_path = dir_path.replace(".", "/")
                            url_path = f"{api_prefix}{dir_path}"
                        else:
                            dir_path = router_path.replace(".", "/")
                            url_path = f"{api_prefix}{dir_path}"
                        
                        print(f"Mounting router from {module_name} at {url_path}")
                        logging.info(f"Mounting router from {module_name} at {url_path}")
                        
                        # Show registered routes on the router
                        print(f"Routes on this router:")
                        for route in attr_value.routes:
                            full_path = f"{url_path}{route.path}"
                            print(f"  - {', '.join(route.methods)} {full_path}")
                            logging.info(f"Registered route: {', '.join(route.methods)} {full_path}")
                        
                        app.include_router(attr_value, prefix=url_path)
            except Exception as e:
                error_msg = f"Error importing module {module_name}: {e}"
                print(error_msg)
                logging.error(error_msg)
    
    print("Router discovery complete")
    logging.info("Router discovery complete")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Redis for rate limiting
    redis = await aioredis.from_url("redis://localhost")
    await FastAPILimiter.init(redis)
    yield

app = FastAPI(lifespan=lifespan)

# Add a direct status route - only keep the version without trailing slash
@app.get(f"{API_PREFIX}/status", status_code=status.HTTP_200_OK)
async def direct_status():
    return {"status": "API is online"}

# Add middleware to handle unauthorized requests consistently
@app.middleware("http")
async def check_auth_middleware(request: Request, call_next):
    # Allow status endpoint without auth
    if "/status" in request.url.path:
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
logging.info(f"Starting router discovery with API_PREFIX={API_PREFIX}")
discover_routers(app, API_PREFIX)
logging.info("Router discovery done")

if __name__ == "__main__":
    import uvicorn
    logging.info(f"Starting server on fixed port {API_PORT}")
    # Start with auto-reload enabled
    uvicorn.run(
        "api.main:app", 
        host="0.0.0.0", 
        port=API_PORT,
        reload=True,  # Enable auto-reload
        reload_dirs=["api"]  # Watch only the api directory
    ) 