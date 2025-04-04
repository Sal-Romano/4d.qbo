import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from quickbooks import QuickBooks
from quickbooks.objects.invoice import Invoice
from intuitlib.client import AuthClient
from intuitlib.enums import Scopes
import requests

# Force reload environment variables
load_dotenv(override=True)

# Get configuration from environment
CALLBACK_DOMAIN = os.getenv('QBO_CALLBACK_DOMAIN', 'localhost')
CALLBACK_PORT = os.getenv('QBO_CALLBACK_PORT', '8725')
CALLBACK_PATH = os.getenv('QBO_CALLBACK_PATH', '/callback')
CALLBACK_HOST = os.getenv('QBO_CALLBACK_HOST', '127.0.0.1')

# Build the redirect URI
if CALLBACK_DOMAIN == 'localhost':
    REDIRECT_URI = f"http://{CALLBACK_DOMAIN}:{CALLBACK_PORT}{CALLBACK_PATH}"
else:
    REDIRECT_URI = f"https://{CALLBACK_DOMAIN}{CALLBACK_PATH}"

# Other QBO settings
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
        self.redirect_uri = REDIRECT_URI
        self.token_path = Path('data/qbo_token.json')
        
        print(f"Debug - Using redirect URI: {self.redirect_uri}")
        print(f"Debug - Environment: {self.environment}")
        
        self.auth_client = AuthClient(
            client_id=self.client_id,
            client_secret=self.client_secret,
            environment=self.environment,
            redirect_uri=self.redirect_uri
        )
        
        self.required_scopes = [
            Scopes.ACCOUNTING,
        ]

    def test_token_refresh(self, simulate_days=0):
        """Test token refresh functionality by:
        1. Loading current tokens
        2. Forcing expiration
        3. Attempting a QBO operation to trigger refresh
        
        Args:
            simulate_days (int): Number of days to simulate passing
        """
        print("\nTesting Token Refresh:")
        print("----------------------")
        
        # Load current tokens
        if not self.token_path.exists():
            print("❌ No token file found. Please authenticate first.")
            return False
            
        with open(self.token_path) as f:
            original_token_data = json.load(f)
            print(f"✓ Loaded original token data")
            print(f"  Original expiry: {original_token_data['expires_at']}")
        
        if simulate_days > 0:
            # Simulate passage of time by moving expiration back
            original_expires = datetime.fromisoformat(original_token_data['expires_at'])
            simulated_expires = original_expires - timedelta(days=simulate_days)
            original_token_data['expires_at'] = simulated_expires.isoformat()
            print(f"\n✓ Simulating {simulate_days} days passing...")
            print(f"  New simulated expiry: {simulated_expires}")
        else:
            # Force immediate expiration
            original_token_data['expires_at'] = (datetime.now() - timedelta(hours=1)).isoformat()
            print("✓ Forced token expiration")
            
        with open(self.token_path, 'w') as f:
            json.dump(original_token_data, f, indent=2)
        
        try:
            # Try to list invoices which should trigger a refresh
            print("\nAttempting operation with expired token...")
            invoices = self.list_recent_invoices(1)
            
            # Check if token was refreshed
            with open(self.token_path) as f:
                new_token_data = json.load(f)
            
            if new_token_data['access_token'] != original_token_data['access_token']:
                print("✓ Success! Token was automatically refreshed")
                print(f"  New expiry: {new_token_data['expires_at']}")
                return True
            else:
                print("❌ Token was not refreshed as expected")
                return False
                
        except Exception as e:
            print(f"❌ Error during refresh test: {str(e)}")
            return False

    def list_companies(self):
        """List available companies using the User Info endpoint."""
        headers = {
            'Authorization': f'Bearer {self.auth_client.access_token}',
            'Accept': 'application/json'
        }
        response = requests.get('https://accounts.platform.intuit.com/v1/openid_connect/userinfo', headers=headers)
        if response.status_code == 200:
            return response.json().get('accounts', [])
        return []
        
    def get_authorization_url(self, company_id=None):
        """Get the authorization URL for QBO OAuth."""
        auth_url = self.auth_client.get_authorization_url(self.required_scopes)
        
        # If a specific company ID is provided, add it to the URL
        if company_id:
            auth_url += f"&company_id={company_id}"
            
        return auth_url
        
    def get_tokens(self, auth_code):
        """Exchange authorization code for tokens and save them."""
        self.auth_client.get_bearer_token(auth_code)
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
            print("Token expired or expiring soon. Refreshing...")
            self.auth_client.refresh()
            self._save_tokens()
            print("Token refreshed successfully!")
            
    def get_client(self):
        """Get an authenticated QuickBooks client."""
        self._load_tokens()
        return QuickBooks(
            auth_client=self.auth_client,
            environment=self.environment,
            company_id=self.auth_client.realm_id
        )
        
    def list_recent_invoices(self, count=30):
        """List the most recent invoices."""
        client = self.get_client()
        invoices = Invoice.query(
            f"SELECT * FROM Invoice ORDERBY TxnDate DESC MAXRESULTS {count}",
            qb=client
        )
        
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
                'status': invoice.EmailStatus
            })
        return invoice_list

def main():
    qbo = QBOManager()
    
    print("\nQuickBooks Online Manager")
    print("========================")
    print("\nPlease choose an operation:")
    print("1. Get authorization URL for a specific company")
    print("2. Get general authorization URL")
    print("3. Test token refresh (simulate expired)")
    print("4. Test token refresh (simulate 5 days passed)")
    print("5. List recent invoices")
    
    choice = input("\nEnter your choice (1-5): ")
    
    if choice == "1":
        company_id = input("\nEnter the Company ID (Realm ID) for the company you want to connect to: ")
        auth_url = qbo.get_authorization_url(company_id)
        print(f"\nPlease visit this URL to authorize: \n{auth_url}\n")
        print("After authorization, you'll be redirected to your callback URL.")
        print("The callback server will automatically handle the token exchange.")
    
    elif choice == "2":
        auth_url = qbo.get_authorization_url()
        print(f"\nPlease visit this URL to authorize: \n{auth_url}\n")
        print("After authorization, you'll be redirected to your callback URL.")
        print("The callback server will automatically handle the token exchange.")
    
    elif choice == "3":
        qbo.test_token_refresh()
    
    elif choice == "4":
        qbo.test_token_refresh(simulate_days=5)
    
    elif choice == "5":
        try:
            print("\nFetching recent invoices...")
            invoices = qbo.list_recent_invoices()
            print(f"\nFound {len(invoices)} invoices:")
            for invoice in invoices:
                print(f"\nInvoice #{invoice['doc_number']}")
                print(f"Customer: {invoice['customer_ref']}")
                print(f"Amount: ${invoice['total_amount']:.2f}")
                print(f"Balance: ${invoice['balance']:.2f}")
                print(f"Date: {invoice['date']}")
                print(f"Due Date: {invoice['due_date']}")
                print(f"Status: {invoice['status']}")
        except FileNotFoundError:
            print("\nPlease authenticate first by getting and visiting an authorization URL.")
        except Exception as e:
            print(f"\nError: {e}")
    
    else:
        print("\nInvalid choice!")

if __name__ == "__main__":
    main()
