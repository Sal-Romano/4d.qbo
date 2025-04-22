from typing import List, Dict, Any
import json
import logging
import httpx
import asyncio
from .qbo import QBOManager

class SyncProcessor:
    def __init__(self, api_key: str, verbose: bool = False):
        self.api_key = api_key
        self.qbo = QBOManager(api_key=api_key)
        self.verbose = verbose
        # QBO allows 40 requests per minute, so we'll space them out
        self.batch_delay = 1.5  # 1.5 seconds between requests (40 per minute)
        self.max_retries = 3
        self.retry_delay = 60  # Wait 60 seconds after hitting rate limit
        # Map standard service items to QuickBooks IDs
        self.service_items = {
            "Anesthesia Fee": {"value": "68", "name": "Anesthesia Fee"},
            "OR Facility Fee": {"value": "65", "name": "OR Facility Fee"},
            "Supplies Charge": {"value": "66", "name": "Supplies Charge"},
            "Procedure": {"value": "1010000021", "name": "Procedure"}
        }
        
    def get_item_ref(self, item: Dict[str, Any]) -> Dict[str, str]:
        """Get the QuickBooks item reference for a line item."""
        # If it's a procedure, use the standard procedure item
        if "Procedure" in item.get("Description", ""):
            return self.service_items["Procedure"]
            
        # For standard service items, try to match by description
        for service_name, item_ref in self.service_items.items():
            if service_name in item.get("Description", ""):
                return item_ref
                
        # Default to using description if no mapping found
        logging.warning(f"No item mapping found for item: {item}")
        return {"name": item.get("Description", "Unknown")}
        
    def create_line_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create properly formatted line items for QuickBooks."""
        line_items = []
        for item in items:
            # Preserve the original line item structure since ItemRef is already set
            line_items.append({
                "DetailType": "SalesItemLineDetail",
                "Amount": item["Amount"],
                "Description": item["Description"],
                "SalesItemLineDetail": {
                    "ItemRef": item["SalesItemLineDetail"]["ItemRef"]
                }
            })
        return line_items
        
    async def execute_batch_with_retry(self, batch_request: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a batch request with retry logic for rate limits."""
        for attempt in range(self.max_retries):
            try:
                if attempt > 0:
                    logging.info(f"Retry attempt {attempt} for batch request")
                
                batch_response = await self.qbo.execute_batch(batch_request)
                
                # Add standard delay between successful requests
                await asyncio.sleep(self.batch_delay)
                
                return batch_response
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:  # Too Many Requests
                    if attempt < self.max_retries - 1:
                        retry_after = int(e.response.headers.get('Retry-After', self.retry_delay))
                        logging.warning(f"Rate limit hit, waiting {retry_after} seconds before retry {attempt + 1}")
                        await asyncio.sleep(retry_after)
                        continue
                    else:
                        logging.error("Max retries reached for rate limit")
                raise
            except Exception as e:
                logging.error(f"Error executing batch request: {str(e)}")
                raise

    async def process_commands(self, commands: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process commands and return results."""
        results = []
        batch_operations = []  # Track operations that need to be executed
        
        # First pass: Check existing invoices
        for command in commands:
            result = {
                "invoice_number": command["invoice_number"],
                "status": command["status"],
                "synced": False,  # Default to not synced
                "action": "No Action"  # Default action
            }
            results.append(result)
            
            # Add invoice check to batch - queries only need bId and Query
            batch_operations.append({
                "bId": str(len(results)),
                "Query": f"SELECT * FROM Invoice WHERE DocNumber = '{command['invoice_number']}'"
            })
            
        # Execute batches in chunks of 30 (QBO limit)
        while batch_operations:
            chunk = batch_operations[:30]
            batch_operations = batch_operations[30:]
            
            batch_request = {
                "BatchItemRequest": []
            }
            
            for op in chunk:
                if "Query" in op:
                    batch_request["BatchItemRequest"].append({
                        "bId": op["bId"],
                        "Query": op["Query"]
                    })
                elif "operation" in op:
                    if op["operation"] == "delete":
                        batch_request["BatchItemRequest"].append({
                            "bId": op["bId"],
                            "operation": "delete",
                            "Invoice": {
                                "Id": op["Id"],
                                "SyncToken": op["SyncToken"]
                            }
                        })
                    elif op["operation"] == "create":
                        if "Customer" in op:
                            batch_request["BatchItemRequest"].append({
                                "bId": op["bId"],
                                "operation": "create",
                                "Customer": op["Customer"]
                            })
                        elif "Invoice" in op:
                            batch_request["BatchItemRequest"].append({
                                "bId": op["bId"],
                                "operation": "create",
                                "Invoice": op["Invoice"]
                            })
            
            if not batch_request["BatchItemRequest"]:
                continue
                
            if self.verbose:
                logging.info(f"Sending batch request: {json.dumps(batch_request, indent=2)}")
            else:
                ops = [op.get("operation", "query") for op in batch_request["BatchItemRequest"]]
                logging.info(f"Sending batch request with operations: {ops}")
            
            try:
                batch_response = await self.execute_batch_with_retry(batch_request)
                
                if not isinstance(batch_response, dict):
                    logging.error(f"Invalid batch response type: {type(batch_response)}")
                    continue
                    
                if "Fault" in batch_response:
                    fault = batch_response["Fault"]
                    error = fault.get("Error", [{}])[0].get("Message", "Unknown error")
                    error_code = fault.get("Error", [{}])[0].get("code", "Unknown code")
                    logging.error(f"Batch request failed with error code {error_code}: {error}")
                    continue
                    
                batch_items = batch_response.get("BatchItemResponse", [])
                if not batch_items:
                    logging.error("No batch items in response")
                    continue
                
                for response in batch_items:
                    try:
                        b_id = response.get("bId")
                        if not b_id:
                            logging.error("Missing bId in response")
                            continue
                            
                        operation = next((op for op in chunk if op["bId"] == b_id), None)
                        if not operation:
                            logging.error(f"No matching operation found for bId {b_id}")
                            if self.verbose:
                                logging.info(f"Current chunk: {json.dumps(chunk, indent=2)}")
                            continue
                            
                        if "Query" in operation:
                            query_response = response.get("QueryResponse", {})
                            command_idx = int(b_id.split("_")[0]) - 1
                            command = commands[command_idx]
                            result = results[command_idx]
                            
                            if "Invoice" in operation["Query"]:
                                invoice_exists = "Invoice" in query_response and query_response["Invoice"]
                                if invoice_exists:
                                    if command["status"] in ["inactive", "active"]:
                                        invoice = query_response.get("Invoice")[0]
                                        if invoice and invoice.get("Id") and invoice.get("SyncToken"):
                                            batch_operations.append({
                                                "bId": f"{b_id}_delete",
                                                "operation": "delete",
                                                "Id": invoice["Id"],
                                                "SyncToken": invoice["SyncToken"]
                                            })
                                            result["synced"] = False  # Will be set to true after deletion
                                            result["action"] = "Will delete from QBO"
                                            logging.info(f"Will delete invoice {invoice['Id']}")
                                        else:
                                            result["synced"] = False
                                            result["action"] = "Failed: Invoice exists but details not available for deletion"
                                            logging.error("Invoice exists but details not available for deletion")
                                    else:
                                        result["synced"] = True
                                        result["action"] = "No Action"
                                        logging.info(f"Invoice {command['invoice_number']} exists and status matches")
                                else:
                                    if command["status"] == "completed":
                                        batch_operations.append({
                                            "bId": f"{b_id}_customer",
                                            "Query": f"SELECT * FROM Customer WHERE DisplayName = '{command['customer']}'"
                                        })
                                        logging.info(f"No invoice found, checking customer {command['customer']}")
                                    else:
                                        result["synced"] = True
                                        result["action"] = "No Action"
                                        logging.info(f"No invoice found for {command['invoice_number']}, status is {command['status']}")
                                        
                            elif "Customer" in operation["Query"]:
                                customers = query_response.get("Customer", [])
                                if customers:
                                    customer = customers[0]
                                    invoice_payload = {
                                        "bId": f"{b_id}_invoice",
                                        "operation": "create",
                                        "Invoice": {
                                            "CustomerRef": {
                                                "value": customer["Id"],
                                                "name": customer["DisplayName"]
                                            },
                                            "TxnDate": command["date"],
                                            "DocNumber": command["invoice_number"],
                                            "Line": self.create_line_items(command["lineitems"]),
                                            "CustomField": [
                                                {
                                                    "DefinitionId": "3",
                                                    "Name": "Quote Version",
                                                    "Type": "StringType",
                                                    "StringValue": str(command.get("version", "1"))
                                                },
                                                {
                                                    "DefinitionId": "2",
                                                    "Name": "Quoted By",
                                                    "Type": "StringType",
                                                    "StringValue": command.get("quoted_by", "")
                                                }
                                            ]
                                        }
                                    }
                                    batch_operations.append(invoice_payload)
                                    logging.info(f"Found customer {customer['DisplayName']}, creating invoice with version {command.get('version', '1')}")
                                else:
                                    batch_operations.append({
                                        "bId": f"{b_id}_create",
                                        "operation": "create",
                                        "Customer": {
                                            "DisplayName": command["customer"]
                                        }
                                    })
                                    logging.info(f"Customer {command['customer']} not found, will create")
                                    
                        elif "operation" in operation:
                            if "Fault" in response:
                                error = response["Fault"].get("Error", [{}])[0]
                                error_message = error.get("Message", "Unknown error")
                                error_code = error.get("code", "Unknown code")
                                error_detail = error.get("Detail", "")
                                
                                # Check for duplicate document number error
                                if "Duplicate" in error_message and "DocNumber" in error_message:
                                    error_message = f"Duplicate invoice number detected: {command['invoice_number']}"
                                    logging.warning(error_message)
                                else:
                                    logging.error(f"Operation failed with error code {error_code}: {error_message}")
                                    if error_detail:
                                        logging.error(f"Error detail: {error_detail}")
                                
                                command_idx = int(b_id.split("_")[0]) - 1
                                results[command_idx]["synced"] = False
                                results[command_idx]["action"] = f"Failed: {error_message}"
                                results[command_idx]["error_code"] = error_code
                                results[command_idx]["error_detail"] = error_detail
                            else:
                                entity_type = "Customer" if "Customer" in operation else "Invoice"
                                if operation["operation"] == "delete":
                                    command_idx = int(b_id.split("_")[0]) - 1
                                    results[command_idx]["synced"] = True
                                    results[command_idx]["action"] = "Deleted Invoice from QBO"
                                    logging.info(f"Successfully deleted invoice {operation.get('Id')}")
                                else:
                                    entity = response.get(entity_type)
                                    if entity:
                                        command_idx = int(b_id.split("_")[0]) - 1
                                        results[command_idx]["synced"] = True
                                        if entity_type == "Customer":
                                            # Create invoice with custom fields for Version and Quoted By
                                            invoice_payload = {
                                                "bId": f"{b_id}_invoice",
                                                "operation": "create",
                                                "Invoice": {
                                                    "CustomerRef": {
                                                        "value": entity["Id"],
                                                        "name": entity["DisplayName"]
                                                    },
                                                    "TxnDate": command["date"],
                                                    "DocNumber": command["invoice_number"],
                                                    "Line": self.create_line_items(command["lineitems"]),
                                                    "CustomField": [
                                                        {
                                                            "DefinitionId": "1",
                                                            "Name": "Quote Version",
                                                            "Type": "StringType",
                                                            "StringValue": str(command.get("version", "1"))
                                                        },
                                                        {
                                                            "DefinitionId": "2",
                                                            "Name": "Quoted By",
                                                            "Type": "StringType",
                                                            "StringValue": command.get("quoted_by", "")
                                                        }
                                                    ]
                                                }
                                            }
                                            batch_operations.append(invoice_payload)
                                            results[command_idx]["action"] = "Creating Customer and Invoice in QBO"
                                            logging.info(f"Created customer {entity['DisplayName']}, creating invoice with version {command.get('version', '1')}")
                                        else:
                                            results[command_idx]["action"] = "Created Invoice in QBO"
                                            logging.info(f"Created invoice {entity['DocNumber']}")
                                    else:
                                        logging.error(f"Operation response missing {entity_type}")
                                        command_idx = int(b_id.split("_")[0]) - 1
                                        results[command_idx]["synced"] = False
                                        results[command_idx]["action"] = f"Failed: Missing {entity_type} in response"
                        
                    except Exception as e:
                        logging.error(f"Error processing response item: {str(e)}")
                        continue
                            
            except Exception as e:
                logging.error(f"Error processing batch: {str(e)}")
                continue
        
        return results
    
    def save_results(self, results: List[Dict[str, Any]], filepath: str):
        """Save processing results to a file."""
        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2)
            
    def all_results_good(self, results: List[Dict[str, Any]]) -> bool:
        """Check if all results have synced status true."""
        return all(result["synced"] for result in results) 