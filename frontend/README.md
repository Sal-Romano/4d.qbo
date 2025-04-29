# 4D EMR to QuickBooks Online Dashboard

This is the frontend dashboard for the 4D EMR to QuickBooks Online integration. It provides a simple interface to monitor sync results and initiate manual syncs.

## Features

- View sync results
- Trigger manual syncs
- Monitor sync history

## Development Setup

1. Install dependencies:
   ```bash
   npm install
   ```

2. Start the development server:
   ```bash
   npm run dev
   ```
   This will start the server with auto-compilation on file changes.

## Production Deployment

1. Build the production assets:
   ```bash
   npm run build
   ```

2. Copy the Nginx configuration:
   ```bash
   sudo cp nginx.conf /etc/nginx/sites-available/sync.voxcon.ai
   sudo ln -s /etc/nginx/sites-available/sync.voxcon.ai /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl reload nginx
   ```

3. Start the production server:
   ```bash
   npm run start
   ```

## API Integration

The dashboard connects to the following API endpoints:

- `/api.v1/sync/initiate`: Initiates the synchronization process
- `/api.v1/status`: Checks API status

## Future Enhancements

- Authentication via Supabase
- Detailed sync logs
- Error tracking
- Schedule management 