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
        self.next_batch_id = 1  # Add counter for generating unique batch IDs
        self.customers_being_created = set()  # Track customers being created
        self.waiting_for_customer = {}  # Track commands waiting for customer creation
        
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
        # Log the full batch request payload for debugging
        logging.info(f"BATCH REQUEST PAYLOAD: {json.dumps(batch_request, indent=2)}")
        
        for attempt in range(self.max_retries):
            try:
                if attempt > 0:
                    logging.info(f"Retry attempt {attempt} for batch request")
                
                batch_response = await self.qbo.execute_batch(batch_request)
                
                # Log full response for debugging
                logging.info(f"BATCH RESPONSE: {json.dumps(batch_response, indent=2)}")
                
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

    def get_next_batch_id(self) -> str:
        """Get next unique batch ID."""
        batch_id = str(self.next_batch_id)
        self.next_batch_id += 1
        return batch_id

    async def process_commands(self, commands: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process commands and return results."""
        results = []
        batch_operations = []  # Track operations that need to be executed
        command_map = {}  # Map batch IDs to command indices
        self.customers_being_created = set()  # Reset tracker for each process run
        created_customers = {}  # Track successfully created customers and their IDs
        self.waiting_for_customer = {}  # Reset waiting commands
        
        # First pass: Check existing invoices
        for i, command in enumerate(commands):
            result = {
                "invoice_number": command["invoice_number"],
                "status": command["status"],
                "synced": False,  # Default to not synced
                "action": "No Action"  # Default action
            }
            results.append(result)
            
            # Add invoice check to batch - queries only need bId and Query
            batch_id = self.get_next_batch_id()
            command_map[batch_id] = i  # Map batch ID to command index
            batch_operations.append({
                "bId": batch_id,
                "Query": f"SELECT * FROM Invoice WHERE DocNumber = '{command['invoice_number']}'"
            })
            
        # Execute batches in chunks of 30 (QBO limit)
        while batch_operations:
            # First prioritize all customer creations in a separate batch
            customer_creates = []
            other_operations = []
            
            for op in batch_operations:
                if "operation" in op and op["operation"] == "create" and "Customer" in op:
                    customer_creates.append(op)
                else:
                    other_operations.append(op)
            
            # If we have customer creations, process those first in a dedicated batch
            if customer_creates:
                logging.info(f"Processing dedicated customer creation batch with {len(customer_creates)} customers")
                chunk = customer_creates[:30]  # Process up to 30 customers at once
                # Remove these from batch_operations
                batch_operations = [op for op in batch_operations if op not in chunk]
                
                batch_request = {
                    "BatchItemRequest": []
                }
                
                for op in chunk:
                    batch_request["BatchItemRequest"].append({
                        "bId": op["bId"],
                        "operation": "create",
                        "Customer": op["Customer"]
                    })
                
                try:
                    if self.verbose:
                        logging.info(f"Sending customer creation batch request: {json.dumps(batch_request, indent=2)}")
                    else:
                        logging.info(f"Sending customer creation batch with {len(chunk)} operations")
                    
                    batch_response = await self.execute_batch_with_retry(batch_request)
                    
                    # Process responses as usual
                    if "BatchItemResponse" in batch_response:
                        for response in batch_response["BatchItemResponse"]:
                            try:
                                b_id = response.get("bId")
                                if not b_id:
                                    logging.error("Missing bId in response")
                                    continue
                                    
                                operation = next((op for op in chunk if op["bId"] == b_id), None)
                                if not operation:
                                    logging.error(f"No matching operation found for bId {b_id}")
                                    continue
                                    
                                command_idx = command_map.get(b_id)
                                if command_idx is None:
                                    logging.error(f"No command index found for bId {b_id}")
                                    continue
                                    
                                command = commands[command_idx]
                                result = results[command_idx]
                                
                                if "Fault" in response:
                                    error = response["Fault"].get("Error", [{}])[0]
                                    error_message = error.get("Message", "Unknown error")
                                    error_code = error.get("code", "Unknown code")
                                    
                                    # If duplicate customer, try to query for it instead
                                    if "Duplicate" in error_message and "name" in error_message.lower():
                                        customer_name = operation["Customer"]["DisplayName"]
                                        logging.info(f"Customer {customer_name} already exists, querying for it")
                                        # Add a query for this customer
                                        new_batch_id = self.get_next_batch_id()
                                        command_map[new_batch_id] = command_idx
                                        batch_operations.append({
                                            "bId": new_batch_id,
                                            "Query": f"SELECT * FROM Customer WHERE DisplayName = '{customer_name}'"
                                        })
                                    else:
                                        logging.error(f"Customer creation failed: {error_message}")
                                        result["synced"] = False
                                        result["action"] = f"Failed: {error_message}"
                                else:
                                    if "Customer" in response:
                                        entity = response["Customer"]
                                        customer_name = entity["DisplayName"]
                                        customer_id = entity["Id"]
                                        created_customers[customer_name] = {
                                            "Id": customer_id,
                                            "DisplayName": customer_name
                                        }
                                        logging.info(f"Successfully created customer {customer_name} with ID {customer_id}")
                                        
                                        # Process any commands that were waiting for this customer
                                        waiting_commands = self.waiting_for_customer.get(customer_name, [])
                                        if waiting_commands:
                                            logging.info(f"Processing {len(waiting_commands)} commands that were waiting for customer {customer_name}")
                                            for waiting_idx in waiting_commands:
                                                waiting_command = commands[waiting_idx]
                                                new_batch_id = self.get_next_batch_id()
                                                command_map[new_batch_id] = waiting_idx
                                                invoice_payload = {
                                                    "bId": new_batch_id,
                                                    "operation": "create",
                                                    "Invoice": {
                                                        "CustomerRef": {
                                                            "value": entity["Id"],
                                                            "name": entity["DisplayName"]
                                                        },
                                                        "TxnDate": waiting_command["date"],
                                                        "DocNumber": waiting_command["invoice_number"],
                                                        "Line": self.create_line_items(waiting_command["lineitems"]),
                                                        "CustomField": [
                                                            {
                                                                "DefinitionId": "1",
                                                                "Name": "Quote Version",
                                                                "Type": "StringType",
                                                                "StringValue": str(waiting_command.get("version", "1"))
                                                            },
                                                            {
                                                                "DefinitionId": "2",
                                                                "Name": "Quoted By",
                                                                "Type": "StringType",
                                                                "StringValue": waiting_command.get("quoted_by", "")
                                                            }
                                                        ]
                                                    }
                                                }
                                                batch_operations.append(invoice_payload)
                                                results[waiting_idx]["action"] = "Creating Invoice after customer creation"
                                            # Clear the waiting list for this customer
                                            self.waiting_for_customer[customer_name] = []
                                        
                                        # Create invoice for the original command too
                                        new_batch_id = self.get_next_batch_id()
                                        command_map[new_batch_id] = command_idx
                                        invoice_payload = {
                                            "bId": new_batch_id,
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
                                        result["action"] = "Creating Invoice after creating customer"
                            except Exception as e:
                                logging.error(f"Error processing customer creation response: {str(e)}")
                                continue
                
                except Exception as e:
                    logging.error(f"Error processing customer creation batch: {str(e)}")
                    # Mark all commands in this batch as failed
                    for op in chunk:
                        command_idx = command_map.get(op["bId"])
                        if command_idx is not None:
                            results[command_idx]["synced"] = False
                            results[command_idx]["action"] = f"Failed: Customer creation error - {str(e)}"
                
                # Add delay after customer batch
                await asyncio.sleep(self.batch_delay)
                continue
            
            # Process other operations in normal batches
            chunk = other_operations[:30]
            batch_operations = [op for op in batch_operations if op not in chunk]
            
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
                            # Skip if this customer is already being created in this or previous batches
                            if op["Customer"]["DisplayName"] in self.customers_being_created:
                                logging.info(f"Skipping duplicate customer creation for {op['Customer']['DisplayName']}")
                                # Mark the corresponding command as needing customer query rather than create
                                command_idx = command_map.get(op["bId"])
                                if command_idx is not None:
                                    new_batch_id = self.get_next_batch_id()
                                    command_map[new_batch_id] = command_idx
                                    batch_operations.append({
                                        "bId": new_batch_id,
                                        "Query": f"SELECT * FROM Customer WHERE DisplayName = '{op['Customer']['DisplayName']}'"
                                    })
                                continue
                            
                            # Track this customer as being created
                            self.customers_being_created.add(op["Customer"]["DisplayName"])
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
                            
                        command_idx = command_map.get(b_id)
                        if command_idx is None:
                            logging.error(f"No command index found for bId {b_id}")
                            continue
                            
                        command = commands[command_idx]
                        result = results[command_idx]
                            
                        if "Query" in operation:
                            query_response = response.get("QueryResponse", {})
                            
                            if "Invoice" in operation["Query"]:
                                invoice_exists = "Invoice" in query_response and query_response["Invoice"]
                                if invoice_exists:
                                    if command["status"] in ["inactive", "active"]:
                                        invoice = query_response.get("Invoice")[0]
                                        if invoice and invoice.get("Id") and invoice.get("SyncToken"):
                                            new_batch_id = self.get_next_batch_id()
                                            command_map[new_batch_id] = command_idx
                                            batch_operations.append({
                                                "bId": new_batch_id,
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
                                        new_batch_id = self.get_next_batch_id()
                                        command_map[new_batch_id] = command_idx
                                        batch_operations.append({
                                            "bId": new_batch_id,
                                            "Query": f"SELECT * FROM Customer WHERE DisplayName = '{command['customer']}'"
                                        })
                                        logging.info(f"No invoice found, checking customer {command['customer']}")
                                    else:
                                        result["synced"] = True
                                        result["action"] = "No Action"
                                        logging.info(f"No invoice found for {command['invoice_number']}, status is {command['status']}")
                                        
                            elif "Customer" in operation["Query"]:
                                customers = query_response.get("Customer", [])
                                customer_name = command["customer"]
                                
                                # First check if we've already created this customer in a previous batch
                                if customer_name in created_customers:
                                    customer = created_customers[customer_name]
                                    logging.info(f"Using previously created customer {customer_name}")
                                    new_batch_id = self.get_next_batch_id()
                                    command_map[new_batch_id] = command_idx
                                    invoice_payload = {
                                        "bId": new_batch_id,
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
                                elif customers:
                                    customer = customers[0]
                                    # Store this customer for future reference
                                    created_customers[customer_name] = customer
                                    
                                    # Process any commands that were waiting for this customer
                                    waiting_commands = self.waiting_for_customer.get(customer_name, [])
                                    if waiting_commands:
                                        logging.info(f"Processing {len(waiting_commands)} commands that were waiting for customer {customer_name}")
                                        for waiting_idx in waiting_commands:
                                            waiting_command = commands[waiting_idx]
                                            new_batch_id = self.get_next_batch_id()
                                            command_map[new_batch_id] = waiting_idx
                                            invoice_payload = {
                                                "bId": new_batch_id,
                                                "operation": "create",
                                                "Invoice": {
                                                    "CustomerRef": {
                                                        "value": customer["Id"],
                                                        "name": customer["DisplayName"]
                                                    },
                                                    "TxnDate": waiting_command["date"],
                                                    "DocNumber": waiting_command["invoice_number"],
                                                    "Line": self.create_line_items(waiting_command["lineitems"]),
                                                    "CustomField": [
                                                        {
                                                            "DefinitionId": "1",
                                                            "Name": "Quote Version",
                                                            "Type": "StringType",
                                                            "StringValue": str(waiting_command.get("version", "1"))
                                                        },
                                                        {
                                                            "DefinitionId": "2",
                                                            "Name": "Quoted By",
                                                            "Type": "StringType",
                                                            "StringValue": waiting_command.get("quoted_by", "")
                                                        }
                                                    ]
                                                }
                                            }
                                            batch_operations.append(invoice_payload)
                                            results[waiting_idx]["action"] = "Creating Invoice for found customer"
                                        # Clear the waiting list for this customer
                                        self.waiting_for_customer[customer_name] = []
                                    
                                    # Create invoice for the current command
                                    new_batch_id = self.get_next_batch_id()
                                    command_map[new_batch_id] = command_idx
                                    invoice_payload = {
                                        "bId": new_batch_id,
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
                                    logging.info(f"Created customer {customer['DisplayName']}, creating invoice with version {command.get('version', '1')}")
                                else:
                                    # Only create the customer if not already being created
                                    if customer_name not in self.customers_being_created:
                                        self.customers_being_created.add(customer_name)
                                        new_batch_id = self.get_next_batch_id()
                                        command_map[new_batch_id] = command_idx
                                        batch_operations.append({
                                            "bId": new_batch_id,
                                            "operation": "create",
                                            "Customer": {
                                                "DisplayName": customer_name
                                            }
                                        })
                                        logging.info(f"Customer {customer_name} not found, will create")
                                    else:
                                        # Customer is being created in another operation
                                        logging.info(f"Customer {customer_name} already queued for creation, waiting for next batch")
                                        # Track that this command is waiting for a customer to be created
                                        if customer_name not in self.waiting_for_customer:
                                            self.waiting_for_customer[customer_name] = []
                                        self.waiting_for_customer[customer_name].append(command_idx)
                        
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
                                
                                results[command_idx]["synced"] = False
                                results[command_idx]["action"] = f"Failed: {error_message}"
                                results[command_idx]["error_code"] = error_code
                                results[command_idx]["error_detail"] = error_detail
                            else:
                                entity_type = "Customer" if "Customer" in operation else "Invoice"
                                if operation["operation"] == "delete":
                                    results[command_idx]["synced"] = True
                                    results[command_idx]["action"] = "Deleted Invoice from QBO"
                                    logging.info(f"Successfully deleted invoice {operation.get('Id')}")
                                else:
                                    entity = response.get(entity_type)
                                    if entity:
                                        if entity_type == "Customer":
                                            # Store created customer for reuse
                                            customer_name = entity["DisplayName"]
                                            customer_id = entity["Id"]
                                            created_customers[customer_name] = {
                                                "Id": customer_id,
                                                "DisplayName": customer_name
                                            }
                                            
                                            # Process any commands that were waiting for this customer
                                            waiting_commands = self.waiting_for_customer.get(customer_name, [])
                                            if waiting_commands:
                                                logging.info(f"Processing {len(waiting_commands)} commands that were waiting for customer {customer_name}")
                                                for waiting_idx in waiting_commands:
                                                    waiting_command = commands[waiting_idx]
                                                    new_batch_id = self.get_next_batch_id()
                                                    command_map[new_batch_id] = waiting_idx
                                                    invoice_payload = {
                                                        "bId": new_batch_id,
                                                        "operation": "create",
                                                        "Invoice": {
                                                            "CustomerRef": {
                                                                "value": entity["Id"],
                                                                "name": entity["DisplayName"]
                                                            },
                                                            "TxnDate": waiting_command["date"],
                                                            "DocNumber": waiting_command["invoice_number"],
                                                            "Line": self.create_line_items(waiting_command["lineitems"]),
                                                            "CustomField": [
                                                                {
                                                                    "DefinitionId": "1",
                                                                    "Name": "Quote Version",
                                                                    "Type": "StringType",
                                                                    "StringValue": str(waiting_command.get("version", "1"))
                                                                },
                                                                {
                                                                    "DefinitionId": "2",
                                                                    "Name": "Quoted By",
                                                                    "Type": "StringType",
                                                                    "StringValue": waiting_command.get("quoted_by", "")
                                                                }
                                                            ]
                                                        }
                                                    }
                                                    batch_operations.append(invoice_payload)
                                                    results[waiting_idx]["action"] = "Creating Invoice for found customer"
                                                # Clear the waiting list for this customer
                                                self.waiting_for_customer[customer_name] = []
                                                
                                            # Create invoice for the current command
                                            new_batch_id = self.get_next_batch_id()
                                            command_map[new_batch_id] = command_idx
                                            invoice_payload = {
                                                "bId": new_batch_id,
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
                                            results[command_idx]["synced"] = True
                                            results[command_idx]["action"] = "Created Invoice in QBO"
                                            logging.info(f"Created invoice {entity['DocNumber']}")
                                    else:
                                        logging.error(f"Operation response missing {entity_type}")
                                        results[command_idx]["synced"] = False
                                        results[command_idx]["action"] = f"Failed: Missing {entity_type} in response"
                            
                    except Exception as e:
                        logging.error(f"Error processing response item: {str(e)}")
                        continue
                            
            except Exception as e:
                logging.error(f"Error processing batch: {str(e)}")
                # Mark all commands in this batch as failed
                for op in chunk:
                    command_idx = command_map.get(op["bId"])
                    if command_idx is not None:
                        results[command_idx]["synced"] = False
                        results[command_idx]["action"] = f"Failed: Batch processing error - {str(e)}"
                        results[command_idx]["error"] = str(e)
                continue
        
        # After all batch processing, if we still have commands waiting for customers, try to look them up directly
        if self.waiting_for_customer:
            waiting_customers = list(self.waiting_for_customer.keys())
            logging.info(f"After all batches, still have commands waiting for customers: {waiting_customers}")
            
            # Try to look up each customer one more time before giving up
            for customer_name in waiting_customers:
                if not self.waiting_for_customer[customer_name]:
                    continue  # Skip if no commands are waiting
                    
                # Create a special batch just to look up this customer
                lookup_batch_id = self.get_next_batch_id()
                lookup_batch = {
                    "BatchItemRequest": [
                        {
                            "bId": lookup_batch_id,
                            "Query": f"SELECT * FROM Customer WHERE DisplayName = '{customer_name}'"
                        }
                    ]
                }
                
                try:
                    logging.info(f"Final attempt to look up customer: {customer_name}")
                    lookup_response = await self.execute_batch_with_retry(lookup_batch)
                    
                    if "BatchItemResponse" in lookup_response:
                        batch_item = lookup_response["BatchItemResponse"][0]
                        if "QueryResponse" in batch_item and "Customer" in batch_item["QueryResponse"]:
                            customers = batch_item["QueryResponse"]["Customer"]
                            if customers:
                                customer = customers[0]
                                customer_id = customer["Id"]
                                logging.info(f"Found customer on final lookup: {customer_name} with ID {customer_id}")
                                
                                # Process all waiting commands for this customer
                                waiting_commands = self.waiting_for_customer[customer_name]
                                if waiting_commands:
                                    invoice_batch = {
                                        "BatchItemRequest": []
                                    }
                                    
                                    for waiting_idx in waiting_commands:
                                        waiting_command = commands[waiting_idx]
                                        new_batch_id = self.get_next_batch_id()
                                        command_map[new_batch_id] = waiting_idx
                                        
                                        invoice_payload = {
                                            "bId": new_batch_id,
                                            "operation": "create",
                                            "Invoice": {
                                                "CustomerRef": {
                                                    "value": customer_id,
                                                    "name": customer_name
                                                },
                                                "TxnDate": waiting_command["date"],
                                                "DocNumber": waiting_command["invoice_number"],
                                                "Line": self.create_line_items(waiting_command["lineitems"]),
                                                "CustomField": [
                                                    {
                                                        "DefinitionId": "1",
                                                        "Name": "Quote Version",
                                                        "Type": "StringType",
                                                        "StringValue": str(waiting_command.get("version", "1"))
                                                    },
                                                    {
                                                        "DefinitionId": "2",
                                                        "Name": "Quoted By",
                                                        "Type": "StringType",
                                                        "StringValue": waiting_command.get("quoted_by", "")
                                                    }
                                                ]
                                            }
                                        }
                                        invoice_batch["BatchItemRequest"].append(invoice_payload)
                                        results[waiting_idx]["action"] = "Creating Invoice in final batch"
                                    
                                    if invoice_batch["BatchItemRequest"]:
                                        logging.info(f"Processing final invoice batch for customer {customer_name}")
                                        final_response = await self.execute_batch_with_retry(invoice_batch)
                                        
                                        # Process the responses
                                        if "BatchItemResponse" in final_response:
                                            for item in final_response["BatchItemResponse"]:
                                                if "bId" in item:
                                                    item_idx = command_map.get(item["bId"])
                                                    if item_idx is not None:
                                                        if "Fault" not in item and "Invoice" in item:
                                                            results[item_idx]["synced"] = True
                                                            results[item_idx]["action"] = "Created Invoice in final batch"
                                                        else:
                                                            results[item_idx]["synced"] = False
                                                            error_msg = "Unknown error in final batch"
                                                            if "Fault" in item and "Error" in item["Fault"]:
                                                                error_msg = item["Fault"]["Error"][0].get("Message", error_msg)
                                                            results[item_idx]["action"] = f"Failed in final batch: {error_msg}"
                            else:
                                logging.error(f"Customer still not found in final lookup: {customer_name}")
                                # Mark all waiting commands as failed
                                for waiting_idx in self.waiting_for_customer[customer_name]:
                                    results[waiting_idx]["synced"] = False
                                    results[waiting_idx]["action"] = f"Failed: Customer {customer_name} could not be created or found"
                
                except Exception as e:
                    logging.error(f"Error in final customer lookup for {customer_name}: {str(e)}")
                    # Mark all waiting commands as failed
                    for waiting_idx in self.waiting_for_customer[customer_name]:
                        results[waiting_idx]["synced"] = False
                        results[waiting_idx]["action"] = f"Failed: Error in final customer lookup - {str(e)}"
        
        return results
    
    def save_results(self, results: List[Dict[str, Any]], filepath: str):
        """Save processing results to a file."""
        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2)
            
    def all_results_good(self, results: List[Dict[str, Any]]) -> bool:
        """Check if all results have synced status true."""
        all_good = True
        success_count = 0
        failure_count = 0
        active_count = 0
        completed_count = 0
        inactive_count = 0
        
        for i, result in enumerate(results):
            if result.get("synced", False):
                success_count += 1
            else:
                failure_count += 1
                logging.error(f"Failed command: Invoice #{result.get('invoice_number')}, Status: {result.get('status')}, Action: {result.get('action')}, Index: {i}")
                all_good = False
            
            # Track counts by status
            status = result.get("status", "unknown")
            if status == "active":
                active_count += 1
            elif status == "completed":
                completed_count += 1
            elif status == "inactive":
                inactive_count += 1
        
        total = len(results)
        logging.info(f"Processing summary: {success_count}/{total} successful ({failure_count} failures)")
        logging.info(f"Status breakdown: {active_count} active, {completed_count} completed, {inactive_count} inactive")
        
        # List all waiting customers if any
        if self.waiting_for_customer:
            waiting_count = sum(len(cmds) for cmds in self.waiting_for_customer.values())
            if waiting_count > 0:
                logging.error(f"Still have {waiting_count} commands waiting for customers: {list(self.waiting_for_customer.keys())}")
        
        return all_good 