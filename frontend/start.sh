#!/bin/bash

# Change to the frontend directory
cd "$(dirname "$0")" || exit

# Build the frontend
echo "Building frontend..."
npm run build

# Start the server
echo "Starting frontend server on port 9743..."
npx vite preview --host 0.0.0.0 --port 9743 --strictPort 