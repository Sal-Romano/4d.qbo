from fastapi import FastAPI, HTTPException, Header, Depends, status
from fastapi.security import APIKeyHeader
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI()

API_KEY = os.getenv("API_KEY")
API_KEY_NAME = "secret" # Name of the header to check
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

API_PORT = int(os.getenv("API_PORT", 9742))  # Default to 9742 if not set

async def get_api_key(key: str = Depends(api_key_header)):
    if key == API_KEY:
        return key
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Bearer"}, # Optional, typically used for Bearer tokens but sets the context
        )

# Allow both GET and HEAD requests for the status endpoint
@app.api_route("/status", methods=["GET", "HEAD"], status_code=status.HTTP_200_OK)
def read_status():
    # For HEAD requests, FastAPI/Starlette automatically returns only headers
    return {"status": "API is online"}

@app.get("/test", dependencies=[Depends(get_api_key)], status_code=status.HTTP_200_OK)
def read_test():
    # If execution reaches here, the API key is valid
    return {"message": "Authorized"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=API_PORT) 