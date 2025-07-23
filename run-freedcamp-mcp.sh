#!/bin/bash
# Wrapper script for running Freedcamp MCP in Docker
# This script is used by Claude Desktop to communicate with the containerized MCP server

# Check if API credentials are provided as arguments or environment variables
if [ -n "$1" ] && [ -n "$2" ]; then
    export FREEDCAMP_API_KEY="$1"
    export FREEDCAMP_API_SECRET="$2"
fi

# Ensure the image is built
docker build -t freedcamp-mcp:latest "$(dirname "$0")" 2>/dev/null

# Run the container interactively with stdio forwarding
# --rm: Remove container after exit
# -i: Keep stdin open (required for MCP)
# --log-driver none: Disable logging to prevent interference with stdio
exec docker run --rm -i \
    --log-driver none \
    -e FREEDCAMP_API_KEY="${FREEDCAMP_API_KEY}" \
    -e FREEDCAMP_API_SECRET="${FREEDCAMP_API_SECRET}" \
    freedcamp-mcp:latest
