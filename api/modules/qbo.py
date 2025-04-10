import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from quickbooks import QuickBooks
from quickbooks.objects.estimate import Estimate
from quickbooks.objects.invoice import Invoice
from quickbooks.objects.customer import Customer
from intuitlib.client import AuthClient
from intuitlib.enums import Scopes
import requests
import logging
import xml.etree.ElementTree as ET

# Force reload environment variables
load_dotenv(override=True)

# Get configuration from environment
CLIENT_ID = os.getenv('QBO_CLIENT_ID')
CLIENT_SECRET = os.getenv('QBO_CLIENT_SECRET')
ENVIRONMENT = os.getenv('QBO_ENVIRONMENT', 'production')

class QBOManager:
    def __init__(self):
        if not all([CLIENT_ID, CLIENT_SECRET]):
            raise ValueError("QBO_CLIENT_ID and QBO_CLIENT_SECRET must be set in .env file")
            
        self.client_id = CLIENT_ID
        self.client_secret = CLIENT_SECRET
        self.environment = ENVIRONMENT
        self.token_path = Path('data/qbo_token.json')
        
        self.auth_client = AuthClient(
            client_id=self.client_id,
            client_secret=self.client_secret,
            environment=self.environment,
            redirect_uri="http://localhost"
        )
        
        self.required_scopes = [
            Scopes.ACCOUNTING,
        ]

    def _load_tokens(self):
        """Load tokens from file."""
        if not self.token_path.exists():
            raise FileNotFoundError("Token file not found. Please authenticate first.")
            
        with open(self.token_path) as f:
            token_data = json.load(f)
            
        self.auth_client.access_token = token_data['access_token']
        self.auth_client.refresh_token = token_data['refresh_token']
        self.auth_client.realm_id = token_data.get('realm_id')
        expires_at = datetime.fromisoformat(token_data['expires_at'])
        
        # Refresh token if expired or about to expire
        if datetime.now() + timedelta(minutes=5) >= expires_at:
            self.auth_client.refresh()
            self._save_tokens()

    def _save_tokens(self):
        """Save tokens to file."""
        token_data = {
            'access_token': self.auth_client.access_token,
            'refresh_token': self.auth_client.refresh_token,
            'expires_at': (datetime.now() + timedelta(seconds=self.auth_client.expires_in)).isoformat(),
            'realm_id': self.auth_client.realm_id
        }
        
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.token_path, 'w') as f:
            json.dump(token_data, f, indent=2)

    def get_client(self):
        """Get an authenticated QuickBooks client."""
        self._load_tokens()
        return QuickBooks(
            auth_client=self.auth_client,
            environment=self.environment,
            company_id=self.auth_client.realm_id
        )

    def list_estimates(self, from_date: str):
        """List estimates from a given date."""
        client = self.get_client()
        query = f"SELECT * FROM Estimate WHERE TxnDate >= '{from_date}' ORDERBY TxnDate DESC"
        estimates = Estimate.query(query, qb=client)
        
        estimate_list = []
        for estimate in estimates:
            estimate_list.append({
                'id': estimate.Id,
                'doc_number': estimate.DocNumber,
                'customer_ref': estimate.CustomerRef.name if estimate.CustomerRef else None,
                'total_amount': float(estimate.TotalAmt) if estimate.TotalAmt else 0.0,
                'date': estimate.TxnDate,
                'status': estimate.EmailStatus
            })
        return estimate_list

    def list_invoices(self, from_date: str):
        """List invoices modified from a given date."""
        client = self.get_client()
        query = f"SELECT * FROM Invoice WHERE MetaData.LastUpdatedTime >= '{from_date}' ORDERBY MetaData.LastUpdatedTime DESC"
        invoices = Invoice.query(query, qb=client)
        
        invoice_list = []
        for invoice in invoices:
            invoice_list.append({
                'id': invoice.Id,
                'doc_number': invoice.DocNumber,
                'customer_ref': invoice.CustomerRef.name if invoice.CustomerRef else None,
                'total_amount': float(invoice.TotalAmt) if invoice.TotalAmt else 0.0,
                'balance': float(invoice.Balance) if invoice.Balance else 0.0,
                'date': invoice.TxnDate,
                'due_date': invoice.DueDate,
                'status': invoice.EmailStatus,
                'last_updated_time': invoice.MetaData.LastUpdatedTime
            })
        return invoice_list

    def get_customer_by_display_name(self, display_name: str):
        """Get a customer by DisplayName."""
        client = self.get_client()
        query = f"SELECT * FROM Customer WHERE DisplayName = '{display_name}'"
        customers = Customer.query(query, qb=client)
        
        if not customers:
            return None
        
        customer = customers[0]
        return {
            'id': customer.Id,
            'display_name': customer.DisplayName,
            'primary_email': customer.PrimaryEmailAddr.Address if customer.PrimaryEmailAddr else None,
            'balance': float(customer.Balance) if customer.Balance else 0.0,
            'active': customer.Active
        }

    def send_batch_request(self, batch_payload):
        """Send a batch request to the QuickBooks Online API."""
        self._load_tokens()
        client = QuickBooks(
            auth_client=self.auth_client,
            environment=self.environment,
            company_id=self.auth_client.realm_id
        )
        url = f"https://quickbooks.api.intuit.com/v3/company/{client.company_id}/batch"
        headers = {
            'Authorization': f'Bearer {client.auth_client.access_token}',
            'Content-Type': 'application/json'
        }
        response = requests.post(url, headers=headers, json=batch_payload)
        
        # Log the status code and raw response content
        logging.info(f"Response status code: {response.status_code}")
        logging.info(f"Response URL: {response.url}")
        
        response.raise_for_status()
        
        # Parse the XML response
        root = ET.fromstring(response.text)
        batch_item_responses = []
        
        for batch_item in root.findall('.//{http://schema.intuit.com/finance/v3}BatchItemResponse'):
            bId = batch_item.get('bId')
            fault = batch_item.find('.//{http://schema.intuit.com/finance/v3}Fault')
            if fault is None:
                # Success case
                entity = batch_item[0]  # Get the first child element, which is the entity
                entity_info = {child.tag.split('}')[1]: child.text for child in entity}
                status = 'success'
                error = None
            else:
                # Failure case
                error_detail = fault.find('.//{http://schema.intuit.com/finance/v3}Detail').text
                entity_info = {}
                status = 'failed'
                error = error_detail
            
            batch_item_responses.append({
                'bId': bId,
                'status': status,
                'error': error,
                'info': entity_info
            })
        
        return {'BatchItemResponse': batch_item_responses} 