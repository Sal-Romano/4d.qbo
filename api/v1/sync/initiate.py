from fastapi import APIRouter, HTTPException, status, Query, Depends
import httpx
import json
import logging
from datetime import datetime, timezone
import os
import time
import asyncio
from fastapi_limiter.depends import RateLimiter
from api.main import get_api_key
from typing import List, Dict, Any
import pytz
from api.modules.sync_processor import SyncProcessor

router = APIRouter()

# Get the absolute path to the project root
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# Rate limiting configuration
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds between retries
REQUEST_DELAY = 0.5  # seconds between regular requests

def convert_to_est(date_str: str) -> str:
    """Convert UTC date string to EST date string in YYYY-MM-DD format."""
    try:
        # First try with microseconds
        utc_dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
    except ValueError:
        # If that fails, try without microseconds
        utc_dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    est_tz = pytz.timezone('America/New_York')
    est_dt = utc_dt.astimezone(est_tz)
    return est_dt.strftime("%Y-%m-%d")

async def make_request_with_retry(client: httpx.AsyncClient, url: str, params: dict, headers: dict) -> dict:
    """Make a request with retry logic for rate limiting."""
    for attempt in range(MAX_RETRIES):
        try:
            # Add delay between requests to respect rate limits
            if attempt > 0:  # Don't delay on first attempt
                await asyncio.sleep(RETRY_DELAY)
            
            response = await client.get(
                url,
                params=params,
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429 and attempt < MAX_RETRIES - 1:
                retry_after = int(e.response.headers.get('Retry-After', RETRY_DELAY))
                logging.info(f"Rate limit hit, waiting {retry_after} seconds before retry {attempt + 1}")
                await asyncio.sleep(retry_after)
                continue
            raise

def get_initials(name: str) -> str:
    """Extract initials from a name."""
    words = [word for word in name.split() if not any(c.isdigit() for c in word)]
    return ''.join(word[0].upper() for word in words if word)

def get_status_code(status_id: int) -> str:
    """Convert status ID to status string."""
    status_map = {0: "inactive", 1: "active", 4: "completed"}
    return status_map.get(status_id, "unknown")

def process_line_items(quote_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Process line items from procedures, supplies, and fees."""
    line_items = []
    
    # Process procedures
    for proc in quote_data.get("Procedures", []):
        line_items.append({
            "DetailType": "SalesItemLineDetail",
            "Amount": proc["Amount"] - (proc.get("DiscountAmount", 0) or 0),
            "Description": proc["ProcedureName"],
            "SalesItemLineDetail": {
                "ItemRef": {
                    "value": "1010000021",
                    "name": "Procedure"
                }
            }
        })
    
    # Process supplies
    for supply in quote_data.get("Supplies", []):
        if supply.get("ShowOnQuote"):
            line_items.append({
                "DetailType": "SalesItemLineDetail",
                "Amount": supply["UnitCost"] * supply["Quantity"],
                "Description": supply["ItemTitle"],
                "SalesItemLineDetail": {
                    "ItemRef": {
                        "value": "66",
                        "name": "Supplies Charge"
                    }
                }
            })
    
    # Add Anesthesia if present
    if quote_data.get("AnesthAmt", 0) > 0:
        anesthesia_group_name = quote_data.get("AnesthesiaGroup", {}).get("Name", "")
        line_items.append({
            "DetailType": "SalesItemLineDetail",
            "Amount": quote_data["AnesthAmt"],
            "Description": f"{anesthesia_group_name} Fee" if anesthesia_group_name else "Anesthesia Fee",
            "SalesItemLineDetail": {
                "ItemRef": {
                    "value": "68",
                    "name": "Anesthesia Fee"
                }
            }
        })
    
    # Add Facility Fee if present
    if quote_data.get("FacilityAmt", 0) > 0:
        line_items.append({
            "DetailType": "SalesItemLineDetail",
            "Amount": quote_data["FacilityAmt"],
            "Description": "PSC Facility Fee",
            "SalesItemLineDetail": {
                "ItemRef": {
                    "value": "65",
                    "name": "OR Facility Fee"
                }
            }
        })
    
    return line_items

@router.get("/initiate", 
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RateLimiter(times=5, seconds=60))])
async def initiate_sync(
    from_date: str = Query(None, description="Starting date in format YYYY-MM-DDTHH:mm:ss (UTC0)"),
    debug: bool = Query(False, description="If true, writes all intermediate files. If false, only writes on error."),
    api_key: str = Depends(get_api_key)
):
    """Initiate sync by requesting quotes and processing them into commands."""
    
    # If from_date not provided, get it from status.json
    if not from_date:
        status_file = os.path.join(PROJECT_ROOT, "api", "data", "ppsa", "status.json")
        try:
            with open(status_file, 'r') as f:
                status_data = json.load(f)
                from_date = status_data.get("last_successful_sync")
                if not from_date:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="No from_date provided and no last successful sync found"
                    )
                # Convert the stored date format to the required format
                try:
                    # Parse the date first (handles both formats)
                    parsed_date = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
                    # Format it in the required format
                    from_date = parsed_date.strftime("%Y-%m-%dT%H:%M:%S")
                except ValueError as e:
                    logging.error(f"Error parsing date from status file: {e}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid date format in status file"
                    )
        except FileNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No from_date provided and no status file found"
            )
    
    # Validate date format
    try:
        datetime.strptime(from_date, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        logging.error(f"Invalid date format: {from_date}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Required format: YYYY-MM-DDTHH:mm:ss"
        )
    
    try:
        # Record sync start time in UTC - format as YYYY-MM-DDTHH:mm:ss
        sync_start_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        
        # Ensure the processing directory exists using absolute path
        processing_dir = os.path.join(PROJECT_ROOT, "api", "data", "ppsa", "processing")
        status_dir = os.path.join(PROJECT_ROOT, "api", "data", "ppsa")
        os.makedirs(processing_dir, exist_ok=True)
        os.makedirs(status_dir, exist_ok=True)
        logging.info(f"Using processing directory: {processing_dir}")
        
        # Generate epoch timestamp for filenames
        epoch_time = int(time.time())
        
        # Initialize file paths
        quotes_file = os.path.join(processing_dir, f"{epoch_time}_quotes.json")
        commands_file = os.path.join(processing_dir, f"{epoch_time}_quotes_commands.json")
        results_file = os.path.join(processing_dir, f"{epoch_time}_quotes_commands_results.json")
        
        # Make an async request to the list_quotes endpoint
        async with httpx.AsyncClient() as client:
            # Get list of quotes
            quotes_url = "http://localhost:9742/api.v1/4demr/list_quotes"
            logging.info(f"Fetching quotes list from: {quotes_url}")
            
            quotes_list = await make_request_with_retry(
                client,
                quotes_url,
                params={"from_date": from_date},
                headers={"secret": api_key}
            )
            
            # Add bId to quotes list
            for i, quote in enumerate(quotes_list, 1):
                quote["bId"] = str(i)
            
            logging.info(f"Retrieved {len(quotes_list)} quotes")
            
            # Save the quotes list with sync time if debug mode
            quotes_data = {
                "sync_time": sync_start_time,
                "quotes": quotes_list
            }
            if debug:
                logging.info(f"Debug mode: Saving quotes to: {quotes_file}")
                with open(quotes_file, 'w') as f:
                    json.dump(quotes_data, f, indent=2)
            
            # Process each quote with rate limiting
            commands = []
            for i, quote in enumerate(quotes_list, 1):
                quote_url = "http://localhost:9742/api.v1/4demr/get_quote"
                logging.info(f"Fetching quote details for {quote['PriceQuoteNo']} from: {quote_url}")
                
                # Add delay between requests
                await asyncio.sleep(REQUEST_DELAY)
                
                quote_data = await make_request_with_retry(
                    client,
                    quote_url,
                    params={"id": quote["PriceQuoteNo"]},
                    headers={"secret": api_key}
                )
                
                # Create command object
                command = {
                    "bId": str(i),
                    "invoice_number": quote["PriceQuoteNo"],
                    "status": get_status_code(quote["PriceQuoteStatus"]["Id"]),
                    "quote_version": quote["Version"],
                    "customer": f"{quote['Patient']['Id']}.{get_initials(quote['Patient']['Name'])}",
                    "lineitems": process_line_items(quote_data),
                    "quoted_by": get_initials(quote_data["CreatedBy"]["Name"]),
                    "date": convert_to_est(quote_data["PriceQuoteDate"])
                }
                commands.append(command)
            
            # Save the commands if in debug mode
            if debug:
                logging.info(f"Debug mode: Saving commands to: {commands_file}")
                with open(commands_file, 'w') as f:
                    json.dump(commands, f, indent=2)
            
            # Process commands with sync processor
            processor = SyncProcessor(api_key)
            results = await processor.process_commands(commands)
            
            # Check if all results are good and update status file
            if processor.all_results_good(results):
                # Update status.json with last successful sync
                status_file = os.path.join(status_dir, "status.json")
                status_data = {
                    "last_successful_sync": sync_start_time
                }
                with open(status_file, 'w') as f:
                    json.dump(status_data, f, indent=2)
                logging.info(f"Updated status file with successful sync time: {sync_start_time}")
                
                # Only save results file if in debug mode
                if debug:
                    processor.save_results(results, results_file)
                    
                return {
                    "detail": "Quotes processed successfully",
                    "results": results,
                    "debug_info": {
                        "quotes_file": f"{epoch_time}_quotes.json",
                        "commands_file": f"{epoch_time}_quotes_commands.json",
                        "results_file": f"{epoch_time}_quotes_commands_results.json",
                        "processing_dir": processing_dir
                    } if debug else None
                }
            else:
                # On error, save all files regardless of debug mode
                with open(quotes_file, 'w') as f:
                    json.dump(quotes_data, f, indent=2)
                with open(commands_file, 'w') as f:
                    json.dump(commands, f, indent=2)
                processor.save_results(results, results_file)
                
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Not all commands were processed successfully"
                )
        
    except httpx.RequestError as e:
        logging.error(f"Request failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve data: {str(e)}"
        )
    except httpx.HTTPStatusError as e:
        logging.error(f"HTTP error occurred: {str(e)}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Error from service: {str(e)}"
        )
    except Exception as e:
        logging.error(f"Error processing quotes: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        ) 