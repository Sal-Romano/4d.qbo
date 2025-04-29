#!/bin/bash

# Change to the frontend directory
cd "$(dirname "$0")" || exit

# Kill any processes using port 9743
echo "Checking for processes on port 9743..."
pid=$(lsof -ti:9743)
if [ -n "$pid" ]; then
  echo "Killing process $pid using port 9743..."
  kill -9 $pid
else
  echo "No process found on port 9743"
fi

# Give the system a moment to release the port
sleep 1

# Start development server with explicit host settings
echo "Starting development server on port 9743..."
npx vite --host 0.0.0.0 --port 9743 --strictPort 