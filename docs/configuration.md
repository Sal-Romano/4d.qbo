# Configuration Guide

This document details all configuration options available in the 4D QuickBooks Online integration.

## Environment Variables

### 4D EMR Configuration
```env
4D_BASE_URL="https://api.4d-emr.com/api/public"  # 4D EMR API endpoint
4D_CLIENT_ID=''                                   # OAuth client ID for 4D EMR
4D_CLIENT_SECRET=''                              # OAuth client secret for 4D EMR
4D_SUBSCRIPTION_KEY=''                           # API subscription key
```

### QuickBooks Online Configuration
```env
QBO_CLIENT_ID=''          # OAuth client ID from Intuit Developer
QBO_CLIENT_SECRET=''      # OAuth client secret from Intuit Developer
QBO_ENVIRONMENT=''        # 'sandbox' or 'production'
```

### Callback Server Configuration
```env
QBO_CALLBACK_DOMAIN=''    # Domain for OAuth callback (localhost for dev, your domain for prod)
QBO_CALLBACK_HOST=''      # Host to bind callback server (default: 127.0.0.1)
QBO_CALLBACK_PORT=8725    # Port for callback server
QBO_CALLBACK_PATH='/callback'  # URL path for OAuth callback
```

### Directory Configuration
```env
LOGS_DIR='logs'          # Directory for log files
```

## Configuration Tips

1. **Development vs Production**
   - Use `sandbox` environment for development
   - Use `production` environment for live QuickBooks data
   - Keep separate `.env` files for each environment

2. **Security Best Practices**
   - Never commit `.env` file to version control
   - Use strong, unique client secrets
   - Rotate secrets periodically
   - Use environment-specific credentials

3. **Logging Configuration**
   - Logs are stored in the directory specified by `LOGS_DIR`
   - Each component writes to its own log file
   - Production logs should be monitored and rotated

4. **OAuth Configuration**
   - Callback server is only needed for initial OAuth setup
   - Tokens are automatically refreshed
   - Different redirect URIs for development and production 