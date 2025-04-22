# 4D EMR <> QuickBooks Online Integration Sync

This project provides a sync bridge between a specific 4D EMR instance and a QuickBooks Online account for automated invoice management and financial synchronization. **It is designed for a single company's use, not as a multi-tenant SaaS solution.** ... yet

## Overview

The core functionality resides in a FastAPI application (`api/main.py`) that serves endpoints (`api/v1`) to handle the synchronization logic. The `scripts/` directory contains utilities for initial setup and testing API connections.

## Requirements

- Python 3.8+
- Access credentials for:
    - 4D EMR API
    - QuickBooks Online API
- A server environment to host the FastAPI application.
- Redis 6.0.16+ 
- Nginx or another reverse proxy

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
│   │   └── ppsa/          # Company/realm directory
│   │       ├── status.json     # Tracks last successful sync
│   │       └── processing/     # Temporary processing directory
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


