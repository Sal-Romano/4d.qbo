from flask import Flask, request, Response
import logging
from qbo_manager import QBOManager
import os
import sys
from dotenv import load_dotenv
import traceback
from pathlib import Path

# Load environment variables
load_dotenv()

# Get configuration from environment
CALLBACK_HOST = os.getenv('QBO_CALLBACK_HOST', '127.0.0.1')
CALLBACK_PORT = int(os.getenv('QBO_CALLBACK_PORT', '8725'))
CALLBACK_PATH = os.getenv('QBO_CALLBACK_PATH', '/callback').lstrip('/')
LOGS_DIR = Path(os.getenv('LOGS_DIR', 'logs'))

# Create logs directory if it doesn't exist
LOGS_DIR.mkdir(exist_ok=True)

# Set up logging to both file and console
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / 'qbo_callback.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
qbo = QBOManager()

@app.route(f'/{CALLBACK_PATH}')
def callback():
    logger.debug("=== Callback Request ===")
    logger.debug(f"Request URL: {request.url}")
    logger.debug(f"Request args: {request.args}")
    logger.debug(f"Request headers: {dict(request.headers)}")
    
    error = request.args.get('error')
    if error:
        logger.error(f"Authorization error: {error}")
        return Response(
            f"Error during authorization: {error}",
            status=400,
            headers={'Content-Type': 'text/html'}
        )
        
    auth_code = request.args.get('code')
    realm_id = request.args.get('realmId')
    
    if not auth_code:
        logger.error("No authorization code received")
        return Response(
            "No authorization code received",
            status=400,
            headers={'Content-Type': 'text/html'}
        )
        
    if not realm_id:
        logger.error("No realm ID received")
        return Response(
            "No realm ID received",
            status=400,
            headers={'Content-Type': 'text/html'}
        )
        
    try:
        logger.info(f"Attempting to exchange auth code for tokens. Realm ID: {realm_id}")
        qbo.auth_client.realm_id = realm_id
        qbo.get_tokens(auth_code)
        
        logger.info("Authorization successful!")
        return Response("""
        <html>
            <body>
                <h1>Authorization Successful!</h1>
                <p>You can now close this window and return to the application.</p>
                <script>
                    setTimeout(function() {
                        window.close();
                    }, 3000);
                </script>
            </body>
        </html>
        """, 
        status=200,
        headers={'Content-Type': 'text/html'}
        )
    except Exception as e:
        logger.error("Error during token exchange:", exc_info=True)
        error_details = traceback.format_exc()
        return Response(
            f"Error exchanging authorization code: {str(e)}<br><pre>{error_details}</pre>",
            status=500,
            headers={'Content-Type': 'text/html'}
        )

@app.route('/')
def home():
    return Response(
        "QuickBooks OAuth Callback Server",
        status=200,
        headers={'Content-Type': 'text/plain'}
    )

if __name__ == '__main__':
    logger.info(f"Starting callback server on {CALLBACK_HOST}:{CALLBACK_PORT}")
    logger.info(f"Callback path: /{CALLBACK_PATH}")
    app.run(host=CALLBACK_HOST, port=CALLBACK_PORT) 