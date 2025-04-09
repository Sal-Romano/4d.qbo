import os
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class FourDManager:
    def __init__(self):
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

    def _make_request(self, endpoint: str, method: str = "GET", params: dict | None = None) -> dict:
        """Helper function to make API requests."""
        url = f"{self.base_url}/{endpoint}"
        try:
            response = requests.request(method, url, headers=self.headers, params=params)
            response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API Request Error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    print(f"Response Body: {e.response.text}")
                except Exception:
                    print("Could not read response body.")
            return {"error": str(e)} # Return a dictionary indicating error

    def list_recent_appointments(self) -> dict:
        """Fetch recent appointments."""
        print("Fetching recent appointments...")
        return self._make_request("appointments")

    def get_patient(self, patient_id: str) -> dict:
        """Fetch patient details by ID."""
        if not patient_id:
            return {"error": "Patient ID cannot be empty."}
        print(f"Fetching patient details for ID: {patient_id}...")
        return self._make_request(f"patients/{patient_id}")


def display_results(data: dict | list):
    """Helper to pretty-print JSON results."""
    import json
    if isinstance(data, dict) and "error" in data:
        print(f"Error: {data['error']}")
    elif data:
        print(json.dumps(data, indent=2))
    else:
        print("No data received or empty response.")

def main():
    try:
        manager = FourDManager()
    except ValueError as e:
        print(f"Initialization Error: {e}")
        return

    print("4D EMR API Manager")
    print("===================")
    print("Please choose an operation:")
    print("1. List recent appointments")
    print("2. Get Patient by ID")

    choice = input("Enter your choice (1-2): ")

    if choice == "1":
        results = manager.list_recent_appointments()
        display_results(results)
    elif choice == "2":
        patient_id = input("Enter the Patient ID: ")
        results = manager.get_patient(patient_id)
        display_results(results)
    else:
        print("Invalid choice!")

if __name__ == "__main__":
    main() 