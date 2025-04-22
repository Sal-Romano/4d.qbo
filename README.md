# 4D EMR <> QuickBooks Online Integration Sync

This project provides a sync bridge between a specific 4D EMR instance and a QuickBooks Online account for automated invoice management and financial synchronization. **It is designed for a single company's use, not as a multi-tenant SaaS solution.** ... yet

## Overview

The core functionality resides in a FastAPI application (`api/main.py`) that will eventually handle the synchronization logic. The `scripts/` directory contains utilities for initial setup and testing API connections.

## Requirements

- Python 3.8+
- Access credentials for:
    - 4D EMR API
    - QuickBooks Online API
- A server environment to host the FastAPI application.
- Redis 6.0.16+ 
- A reverse proxy (like Nginx) is recommended for production.
- A process manager (like systemd) is recommended for production.

## Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/Sal-Romano/4d.qbo
    cd 4d.qbo
    ```

2.  **Install dependencies:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate # Or .\.venv\Scripts\activate on Windows
    pip install -r requirements.txt
    ```

3.  **Configure Environment Variables:**
    - Copy `.env-sample` to `.env`.
    - Fill in the required credentials for 4D EMR (`4D_*`) and QuickBooks Online (`QBO_*`).
    - Set the `API_PORT` for the FastAPI application (default is `9742`).
    - Generate a secure `API_KEY` for accessing protected API endpoints.

4.  **Initial QuickBooks OAuth Setup:**
    - Run the `scripts/qbo_callback_server.py` locally **once** to handle the initial OAuth2 redirect from Intuit.
    - Use `scripts/qbo_manager.py` to generate the authorization URL. Visit this URL, authorize the connection, and the callback server will capture the necessary tokens, saving them to `data/qbo_token.json`.
    - The callback server can be stopped after successful authentication.
    - *Refer to `scripts/qbo_manager.py` usage for details.* The main API will handle token refreshes automatically using the saved tokens.

5.  **Test Connections (Optional but Recommended):**
    - Use `scripts/qbo_manager.py` to test QBO connection and list invoices.
    - Use `scripts/4d_manager.py` to test 4D EMR connection, list appointments, or get patient details.

## Project Structure

```
.
├── api/                    # Main FastAPI application
│   ├── main.py            # Application entry point, auth, and router setup
│   ├── data/              # Persistent data storage
│   │   └── ppsa/          # Price Quote Sync data
│   │       ├── status.json     # Tracks last successful sync
│   │       └── processing/     # Temporary processing files
│   ├── modules/           # Core business logic and integrations
│   │   ├── emr.py         # 4D EMR integration
│   │   ├── qbo.py         # QuickBooks Online integration
│   │   └── sync_processor.py  # Quote to Invoice sync logic
│   └── v1/               # API version 1 endpoints
│       ├── endpoints.py   # Core endpoints (status, test)
│       ├── 4demr/        # 4D EMR specific endpoints
│       ├── qbo/          # QuickBooks Online endpoints
│       └── sync/         # Synchronization endpoints
├── scripts/               # Setup & testing utilities (not for production)
│   ├── qbo_manager.py     # QBO connection testing
│   ├── qbo_callback_server.py  # OAuth setup utility
│   └── 4d_manager.py      # 4D EMR connection testing
├── docs/                  # Documentation
├── logs/                  # Log files
├── .env-sample           # Sample environment configuration
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

The application follows a modular structure where:
- `api/main.py` handles application setup, authentication, and router discovery
- `api/modules/` contains the core business logic and integration code
- `api/v1/` contains all API endpoints, organized by feature
- `api/data/` stores persistent data and processing files
- `scripts/` contains utilities for initial setup and testing (not used in production)

For detailed API endpoint documentation and usage, refer to the API Endpoints section below.

## Running the Application (Production Example)

1.  **FastAPI Server:**
    - The application is run using an ASGI server like Uvicorn.
    - The entry point is `api/main.py`.

2.  **Process Manager (Systemd Example):**
    - Create a service file (e.g., `/etc/systemd/system/4dqbo.service`) to manage the Uvicorn process.
      ```ini
      [Unit]
      Description=4D QBO Sync Service
      After=network.target

      [Service]
      User=<your_service_user> # e.g., www-data
      Group=<your_service_group> # e.g., www-data
      WorkingDirectory=/path/to/your/project/root
      # Ensure .venv is activated or python/uvicorn are globally accessible
      ExecStart=/path/to/your/project/root/.venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 9742
      Restart=always

      [Install]
      WantedBy=multi-user.target
      ```
    - Enable and start the service:
      ```bash
      sudo systemctl enable 4dqbo.service
      sudo systemctl start 4dqbo.service
      ```

3.  **Reverse Proxy (Nginx Example):**
    - Configure Nginx (or another reverse proxy) to handle incoming requests and forward them to the FastAPI application running on the configured `PORT`.
    - Create a site configuration (e.g., `/etc/nginx/sites-available/your-domain.com`):
      ```nginx
      server {
          listen 80;
          server_name your-domain.com; # Replace with your actual domain

          # Optional: Redirect HTTP to HTTPS
          # location / {
          #     return 301 https://$host$request_uri;
          # }

          # If using HTTPS (Recommended):
          # listen 443 ssl;
          # server_name your-domain.com;
          # ssl_certificate /path/to/your/fullchain.pem;
          # ssl_certificate_key /path/to/your/privkey.pem;
          # include /etc/letsencrypt/options-ssl-nginx.conf; # Recommended Certbot options
          # ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem; # Recommended Certbot options

          location / {
              proxy_pass http://127.0.0.1:9742; # Forward to FastAPI
              proxy_set_header Host $host;
              proxy_set_header X-Real-IP $remote_addr;
              proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
              proxy_set_header X-Forwarded-Proto $scheme;
          }
      }
      ```
    - Enable the site and reload Nginx:
      ```bash
      sudo ln -s /etc/nginx/sites-available/your-domain.com /etc/nginx/sites-enabled/
      sudo nginx -t
      sudo systemctl reload nginx
      ```

## API Endpoints

- **`/status`** (GET, HEAD): Public endpoint to check if the API is running. Returns a simple status message.

- **`/test`** (GET): Protected endpoint. Requires a header `secret: <API_KEY>` for authorization. Returns a message confirming authorization.

### QBO Endpoints

- **`/qbo/list_invoices`** (GET): Lists all invoices modified from a given date. Requires a `from_date` query parameter. Times are converted to UTC.

- **`/qbo/list_estimates`** (GET): Lists all estimates from a given date. Requires a `from_date` query parameter. Times are converted to UTC.

- **`/qbo/get_invoice`** (GET): Retrieves a specific invoice by its ID (DocNumber). Requires an `id` query parameter. Times are converted to UTC.

- **`/qbo/batch`** (POST): Posts a batch job to QBO. [Follow QBO /batch payload guidelines](https://www.developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/batch#the-batch-object)

### 4D EMR Endpoints

- **`/4demr/get_patient`** (GET): Retrieves patient details. Requires a `patient_id` query parameter.

- **`/4demr/list_appointments`** (GET): Lists appointments for a given date. Requires a `date` query parameter.

- **`/4demr/list_quotes`** (GET): Lists quotes modified since a given date. Requires a `from_date` query parameter (YYYY-MM-DDTHH:mm:ss format).

- **`/4demr/get_quote`** (GET): Retrieves detailed information for a specific quote. Requires an `id` query parameter (PriceQuoteNo).

### Sync Endpoints

- **`/sync/initiate`** (GET): Initiates the synchronization process between 4D EMR quotes and QuickBooks Online invoices. 
  - **Parameters:**
    - `from_date` (Query, Optional): The start date (YYYY-MM-DDTHH:mm:ss UTC) for fetching quotes. If not provided, it uses the `last_successful_sync` date from `api/data/ppsa/status.json`.
    - `debug` (Query, Optional, bool): If `true`, saves intermediate files (quotes list, commands, results) to the `api/data/ppsa/processing/` directory. If `false` (default), only saves files on error.
  - **Process:**
    1.  Determines the start date for fetching quotes (either from the `from_date` parameter or `status.json`).
    2.  Calls `/api.v1/4demr/list_quotes` to get a list of quotes modified since the start date.
    3.  For each quote in the list:
        - Calls `/api.v1/4demr/get_quote` to retrieve detailed quote information.
        - Processes the quote data (procedures, supplies, fees) into a standardized command format, including line items with appropriate QuickBooks ItemRefs.
        - Assigns a unique batch ID (`bId`) for tracking.
    4.  Instantiates a `SyncProcessor` (from `api/modules/sync_processor.py`).
    5.  Passes the generated list of commands to the `SyncProcessor.process_commands` method.
    6.  The `SyncProcessor` intelligently determines necessary QuickBooks actions (create invoice, delete invoice, no action) based on the quote's status (`active`, `completed`, `inactive`) and whether a corresponding invoice already exists in QuickBooks.
    7.  Executes these actions using the QuickBooks Online Batch API (`/api.v1/qbo/batch`), handling rate limiting and retries automatically.
    8.  If all commands process successfully, updates `api/data/ppsa/status.json` with the current sync time.
    9.  Returns the processing results.
    10. If any command fails or an error occurs, it saves intermediate files (if not already in debug mode) and raises an appropriate HTTP exception.

Note: All QBO endpoints convert times to UTC (Z) for consistency, as they were originally in PST.


