# Development Setup Guide

This guide covers setting up the 4D QuickBooks Online integration for local development.

## Initial Setup

1. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment:
```bash
cp .env-sample .env
```

## QuickBooks Online Configuration

1. Go to [Intuit Developer](https://developer.intuit.com/)
2. Create a new app or select an existing one
3. In the OAuth 2.0 settings:
   - Add `http://localhost:8725/callback` as redirect URI
   - Note your Client ID and Client Secret
4. Update your `.env` file with the credentials:
```env
QBO_CLIENT_ID='your_client_id'
QBO_CLIENT_SECRET='your_client_secret'
QBO_ENVIRONMENT='sandbox'  # Use 'sandbox' for development
QBO_CALLBACK_DOMAIN='localhost'
```

## Running the Integration

1. Start the callback server (for development OAuth flow only):
```bash
python scripts/qbo_callback_server.py
```

2. In a new terminal, run the QBO manager:
```bash
python scripts/qbo_manager.py
```

## Development Tips

- Use the sandbox environment for testing
- Monitor `logs/qbo_callback.log` for OAuth debugging
- The callback server is only needed during initial OAuth setup
- Test token refresh functionality regularly

## Next Steps

- Review [Configuration Guide](configuration.md) for all available options
- Check [Production Setup](production.md) when ready to deploy 