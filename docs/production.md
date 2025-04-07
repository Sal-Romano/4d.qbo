# Production Setup Guide

This guide covers deploying the 4D QuickBooks Online integration to production.

## Prerequisites

- A domain name pointing to your server
- Nginx installed
- Python 3.8+
- Root access for SSL setup

## Initial Setup

1. Clone and set up the project:
```bash
git clone https://github.com/Sal-Romano/4d.qbo.git
cd 4d.qbo
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Configure environment:
```bash
cp .env-sample .env
```

## SSL Certificate Setup

1. Install Certbot:
```bash
sudo apt update
sudo apt install certbot python3-certbot-nginx
```

2. Obtain SSL certificate:
```bash
sudo certbot --nginx -d your-domain.com
```

## Nginx Configuration

Create a new Nginx configuration:
```bash
sudo nano /etc/nginx/sites-available/qbo-callback
```

Add the following configuration:
```nginx
server {
    server_name your-domain.com;

    location /callback {
        proxy_pass http://127.0.0.1:8725;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Certbot will handle SSL configuration
}
```

Enable the site:
```bash
sudo ln -s /etc/nginx/sites-available/qbo-callback /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## Callback Server Service

1. Create a systemd service:
```bash
sudo nano /etc/systemd/system/qbo-callback.service
```

2. Add the configuration:
```ini
[Unit]
Description=QuickBooks Online OAuth Callback Server
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/4d.qbo
Environment=PYTHONPATH=/path/to/4d.qbo
ExecStart=/path/to/4d.qbo/.venv/bin/python scripts/qbo_callback_server.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

3. Start the service:
```bash
sudo systemctl enable qbo-callback
sudo systemctl start qbo-callback
```

## QuickBooks Online Configuration

1. Go to [Intuit Developer](https://developer.intuit.com/)
2. Update your app's OAuth 2.0 settings:
   - Add `https://your-domain.com/callback` as production redirect URI
3. Update your `.env` file:
```env
QBO_CLIENT_ID='your_client_id'
QBO_CLIENT_SECRET='your_client_secret'
QBO_ENVIRONMENT='production'
QBO_CALLBACK_DOMAIN='your-domain.com'
```

## Monitoring

- Nginx logs: `sudo tail -f /var/log/nginx/error.log`
- Callback server logs: 
  - Service logs: `sudo journalctl -u qbo-callback -f`
  - Application logs: `tail -f logs/qbo_callback.log`

## SSL Certificate Renewal

Certbot automatically handles certificate renewal. To test the renewal process:
```bash
sudo certbot renew --dry-run
``` 