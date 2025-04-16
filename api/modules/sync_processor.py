from typing import List, Dict, Any
import json
import logging
import httpx
from .qbo import QBOManager

class SyncProcessor:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.qbo = QBOManager(api_key=api_key)
        
    async def process_commands(self, commands: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process commands and return results."""
        results = []
        batch_operations = []  # Track operations that need to be executed
        
        # First pass: Check existing invoices and customers
        for command in commands:
            result = {
                "invoice_number": command["invoice_number"],
                "status": command["status"],
                "processing_status": "pending"
            }
            results.append(result)
            
            # Add invoice check to batch
            batch_operations.append({
                "bId": str(len(results)),  # Use position as bId
                "operation": "check_invoice",
                "Query": f"SELECT * FROM Invoice WHERE DocNumber = '{command['invoice_number']}'"
            })
            
            # Note: We'll check for customer only after confirming invoice doesn't exist
        
        # Execute batches in chunks of 30 (QBO limit)
        while batch_operations:
            # Get next chunk of operations
            chunk = batch_operations[:30]
            batch_operations = batch_operations[30:]  # Remove processed chunk
            
            # Prepare batch request
            batch_request = {
                "BatchItemRequest": []
            }
            
            # Add operations to batch request
            for op in chunk:
                if op["operation"] in ["check_invoice", "check_customer"]:
                    # Query operations - only need bId and Query
                    batch_request["BatchItemRequest"].append({
                        "bId": op["bId"],
                        "Query": op["Query"]
                    })
                elif op["operation"] == "delete_invoice":
                    # Delete operations
                    batch_request["BatchItemRequest"].append({
                        "bId": op["bId"],
                        "operation": "delete",
                        "Invoice": {
                            "Id": op["Id"],
                            "SyncToken": op["SyncToken"]
                        }
                    })
                elif op["operation"] == "create_customer":
                    # Create customer operations
                    batch_request["BatchItemRequest"].append({
                        "bId": op["bId"],
                        "operation": "create",
                        "Customer": op["payload"]
                    })
                elif op["operation"] == "create_invoice":
                    # Create invoice operations
                    batch_request["BatchItemRequest"].append({
                        "bId": op["bId"],
                        "operation": "create",
                        "Invoice": op["payload"]
                    })
            
            # Skip if no operations in this batch
            if not batch_request["BatchItemRequest"]:
                continue
                
            # Log the batch request for debugging
            logging.info(f"Sending batch request: {json.dumps(batch_request, indent=2)}")
                
            # Execute batch request
            try:
                batch_response = await self.qbo.execute_batch(batch_request)
                
                # Log the full response
                logging.info(f"Received batch response: {json.dumps(batch_response, indent=2)}")
                
                # Ensure we have a valid response structure
                if not isinstance(batch_response, dict):
                    logging.error(f"Invalid batch response type: {type(batch_response)}")
                    continue
                    
                # Check for top-level Fault
                if "Fault" in batch_response:
                    fault = batch_response["Fault"]
                    error = fault.get("Error", [{}])[0].get("Message", "Unknown error")
                    error_code = fault.get("Error", [{}])[0].get("code", "Unknown code")
                    logging.error(f"Batch request failed with error code {error_code}: {error}")
                    continue
                    
                # The response structure has BatchItemResponse as a dict with BatchItemResponse array
                batch_items = batch_response.get("BatchItemResponse", {})
                if isinstance(batch_items, dict):
                    batch_items = batch_items.get("BatchItemResponse", [])
                elif not isinstance(batch_items, list):
                    batch_items = []
                
                if not batch_items:
                    logging.error("No batch items in response")
                    continue
                
                # Process batch responses
                for response in batch_items:
                    try:
                        # Extract bId and operation info
                        b_id = response.get("bId")
                        if not b_id:
                            logging.error("Missing bId in response item")
                            continue
                            
                        operation = next((op for op in chunk if op["bId"] == b_id), None)
                        if not operation:
                            logging.error(f"No matching operation found for bId {b_id}")
                            continue
                            
                        # Check for errors in the response
                        if "Fault" in response:
                            fault = response["Fault"]
                            error = fault.get("Error", [{}])[0].get("Message", "Unknown error")
                            logging.error(f"Error in response for bId {b_id}: {error}")
                            continue
                            
                        # Process response based on operation type
                        if operation["operation"] == "check_invoice":
                            # Handle query responses
                            info = response.get("info", {})
                            # Empty info means no results found
                            # info with Invoice: null means invoice exists but was filtered
                            invoice_exists = "Invoice" in info
                            command_idx = int(b_id) - 1
                            command = commands[command_idx]
                            result = results[command_idx]
                            
                            if invoice_exists:
                                # Invoice exists
                                if command["status"] in ["inactive", "active"]:
                                    # Need to delete invoice
                                    result["processing_status"] = "Mismatch. Will remove from Quickbooks."
                                    invoice = info.get("Invoice")  # Get invoice details if available
                                    if invoice and invoice.get("Id") and invoice.get("SyncToken"):
                                        batch_operations.append({
                                            "bId": f"{b_id}_delete",
                                            "operation": "delete_invoice",
                                            "Id": invoice["Id"],
                                            "SyncToken": invoice["SyncToken"]
                                        })
                                    else:
                                        logging.error(f"Invoice exists but details not available for deletion: {info}")
                                else:
                                    # Invoice exists for completed quote - this is good
                                    result["processing_status"] = "good"
                            else:
                                # No invoice found
                                if command["status"] == "completed":
                                    # For completed quotes with no invoice, check customer
                                    batch_operations.append({
                                        "bId": f"{b_id}_customer",
                                        "operation": "check_customer",
                                        "Query": f"SELECT * FROM Customer WHERE DisplayName = '{command['customer']}'"
                                    })
                                else:
                                    # No invoice for inactive/active quote - this is good
                                    result["processing_status"] = "good"
                                    
                        elif operation["operation"] == "check_customer":
                            # Handle customer query responses
                            info = response.get("info", {})
                            # Empty info means no results found
                            # info with Customer: null means customer exists but was filtered
                            customer_exists = "Customer" in info
                            command_idx = int(b_id.split("_")[0]) - 1
                            command = commands[command_idx]
                            result = results[command_idx]
                            
                            if customer_exists:
                                # Customer exists, create invoice directly
                                batch_operations.append({
                                    "bId": f"{b_id}_invoice",
                                    "operation": "create_invoice",
                                    "payload": {
                                        "CustomerRef": {"name": command["customer"]},  # Use name instead of ID
                                        "TxnDate": command["date"],
                                        "DocNumber": command["invoice_number"],
                                        "Line": command["lineitems"]
                                    }
                                })
                            else:
                                # Need to create customer first
                                batch_operations.append({
                                    "bId": f"{b_id}_create",
                                    "operation": "create_customer",
                                    "payload": {
                                        "DisplayName": command["customer"]
                                    }
                                })
                                
                        elif operation["operation"] == "check_customer_details":
                            # Handle customer details query response
                            info = response.get("info", {})
                            customer = info.get("Customer")
                            command_idx = int(b_id.split("_")[0]) - 1
                            command = commands[command_idx]
                            
                            if customer and customer.get("Id"):
                                # Now we have the customer details, create invoice
                                batch_operations.append({
                                    "bId": f"{b_id}_invoice",
                                    "operation": "create_invoice",
                                    "payload": {
                                        "CustomerRef": {"value": customer["Id"]},
                                        "TxnDate": command["date"],
                                        "DocNumber": command["invoice_number"],
                                        "Line": command["lineitems"]
                                    }
                                })
                            else:
                                logging.error(f"Could not get customer details: {info}")
                                results[command_idx]["processing_status"] = "Failed: Could not get customer details"
                        
                        elif operation["operation"] in ["create_customer", "create_invoice", "delete_invoice"]:
                            # Handle entity creation/deletion responses
                            if response.get("status") == "success":
                                command_idx = int(b_id.split("_")[0]) - 1
                                results[command_idx]["processing_status"] = "good"
                            else:
                                error = response.get("error", "Unknown error")
                                logging.error(f"Operation failed for bId {b_id}: {error}")
                                command_idx = int(b_id.split("_")[0]) - 1
                                results[command_idx]["processing_status"] = f"Failed: {error}"
                        
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
        """Check if all results have 'good' processing status."""
        return all(result["processing_status"] == "good" for result in results) 