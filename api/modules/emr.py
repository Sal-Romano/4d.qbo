"""
Wrapper module for integrating with the 4D EMR system
"""
import os
import sys
import logging
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class FourDManager:
    def __init__(self):
        """Initialize the 4D Manager with credentials from environment variables"""
        self.base_url = os.getenv("4D_BASE_URL")
        self.client_id = os.getenv("4D_CLIENT_ID")
        self.client_secret = os.getenv("4D_CLIENT_SECRET")
        self.subscription_key = os.getenv("4D_SUBSCRIPTION_KEY")

        if not all([self.base_url, self.client_id, self.client_secret, self.subscription_key]):
            raise ValueError("Missing one or more 4D EMR credentials in .env file (4D_BASE_URL, 4D_CLIENT_ID, 4D_CLIENT_SECRET, 4D_SUBSCRIPTION_KEY)")

        self.headers = {
            "client-id": self.client_id,
            "client-secret": self.client_secret,
            "subscription-key": self.subscription_key,
            "Accept": "application/json" # Assuming JSON response is preferred
        }

    def _make_request(self, endpoint: str, method: str = "GET", params: dict = None) -> dict:
        """Helper function to make API requests."""
        url = f"{self.base_url}/{endpoint}"
        try:
            response = requests.request(method, url, headers=self.headers, params=params)
            response.raise_for_status()  # Raises HTTPError for bad responses (4xx or 5xx)
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"API Request Error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    logging.error(f"Response Body: {e.response.text}")
                except Exception:
                    logging.error("Could not read response body.")
            return {"error": str(e)}  # Return a dictionary indicating error

    def list_recent_appointments(self) -> dict:
        """Fetch recent appointments."""
        logging.info("Fetching recent appointments...")
        return self._make_request("appointments")

    def get_patient(self, patient_id: str) -> dict:
        """Fetch patient details by ID."""
        if not patient_id:
            return {"error": "Patient ID cannot be empty."}
        logging.info(f"Fetching patient details for ID: {patient_id}...")
        return self._make_request(f"patients/{patient_id}")
        
    def get_quote(self, quote_id: str) -> dict:
        """Fetch quote details by ID."""
        if not quote_id:
            return {"error": "Quote ID cannot be empty."}
        logging.info(f"Fetching quote details for ID: {quote_id}...")
        return self._make_request("quotes", params={"quoteNumber": quote_id})
        
    def list_quotes(self, from_date: str) -> dict:
        """Fetch quotes list from a specific date.
        
        Args:
            from_date (str): Starting date in format YYYY-MM-DDTHH:mm:ss (UTC0)
        
        Returns:
            dict: List of quotes or error message
        """
        if not from_date:
            return {"error": "From date cannot be empty."}
        
        logging.info(f"Fetching quotes list from date: {from_date}...")
        return self._make_request("quotes/list", params={"fromDate": from_date}) 