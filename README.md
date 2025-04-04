# QuickBooks Online Integration

This project provides a Python-based integration with QuickBooks Online (QBO) API, featuring OAuth2 authentication, automatic token refresh, and invoice management capabilities.

## Prerequisites

- Python 3.8+
- Nginx (if using production setup)
- SSL Certificate (for production)
- QuickBooks Online Developer Account
- A registered QBO app with OAuth2 credentials

## Setup

1. **Clone the repository**
```bash
git clone <repository-url>
cd <repository-name>
```

2. **Create and activate virtual environment**
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure Environment**
```bash
cp .env-sample .env
```
Edit `.env` with your configuration:
```env
# QuickBooks Online API Configuration
QBO_CLIENT_ID=your_client_id_here
QBO_CLIENT_SECRET=your_client_secret_here
QBO_ENVIRONMENT=production  # or sandbox
QBO_CALLBACK_DOMAIN=your-domain.com  # Your callback domain
QBO_CALLBACK_PATH=/callback  # The callback path
QBO_CALLBACK_PORT=8725  # Port for the callback server to listen on
QBO_CALLBACK_HOST=127.0.0.1  # Host for the callback server to listen on

# Nginx Configuration (if using)
NGINX_SSL_CERT_PATH=/etc/letsencrypt/live/your-domain/fullchain.pem
NGINX_SSL_KEY_PATH=/etc/letsencrypt/live/your-domain/privkey.pem
```

## QuickBooks Online App Configuration

1. Go to https://developer.intuit.com/
2. Create a new app or select an existing one
3. Set up OAuth 2.0:
   - Development: Use `http://localhost:8725/callback` as redirect URI
   - Production: Use `https://your-domain.com/callback` as redirect URI
4. Get your Client ID and Client Secret
5. Add these to your `.env` file

## Running the Callback Server

### Development Setup
```bash
# Start the callback server
python scripts/qbo_callback_server.py
```

### Production Setup

1. **Create Nginx configuration**
```bash
sudo nano /etc/nginx/sites-available/qbo-callback
```

Add the following configuration (adjust as needed):
```nginx
server {
    listen 80;
    listen [::]:80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain/privkey.pem;
    
    location /callback {
        proxy_pass http://127.0.0.1:8725;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

2. **Create systemd service**
```bash
sudo nano /etc/systemd/system/qbo-callback.service
```

Add the following configuration:
```ini
[Unit]
Description=QuickBooks Online OAuth Callback Server
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/project
Environment=PYTHONPATH=/path/to/project
ExecStart=/path/to/project/.venv/bin/python /path/to/project/scripts/qbo_callback_server.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

3. **Enable and start the service**
```bash
sudo systemctl enable qbo-callback
sudo systemctl start qbo-callback
```

## Usage

1. **Start the callback server** (if not using systemd)
```bash
python scripts/qbo_callback_server.py
```

2. **Run the QBO manager**
```bash
python scripts/qbo_manager.py
```

The script provides several options:
1. Get authorization URL for a specific company
2. Get general authorization URL
3. Test token refresh (simulate expired)
4. Test token refresh (simulate 5 days passed)
5. List recent invoices

## Token Refresh

Tokens are automatically refreshed when:
- The access token has expired
- The access token is within 5 minutes of expiring
- Any QBO operation is attempted with an expired token

The refresh happens transparently - no manual intervention needed.

## Troubleshooting

1. **Callback not working**
   - Check Nginx logs: `sudo tail -f /var/log/nginx/error.log`
   - Check callback server logs: `sudo journalctl -u qbo-callback -f`
   - Verify SSL certificate is valid
   - Ensure ports are open and forwarded correctly

2. **Token refresh issues**
   - Check token expiration in `data/qbo_token.json`
   - Run token refresh test (Option 3 or 4 in manager)
   - Verify refresh token hasn't expired (100+ days)


