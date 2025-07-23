@echo off
REM Wrapper script for running Freedcamp MCP in Docker (Windows)
REM This script is used by Claude Desktop to communicate with the containerized MCP server

REM Check if API credentials are provided as arguments
if not "%1"=="" if not "%2"=="" (
    set FREEDCAMP_API_KEY=%1
    set FREEDCAMP_API_SECRET=%2
)

REM Ensure the image is built (suppress output)
docker build -t freedcamp-mcp:latest "%~dp0" >nul 2>&1

REM Run the container interactively with stdio forwarding
docker run --rm -i ^
    --log-driver none ^
    -e FREEDCAMP_API_KEY="%FREEDCAMP_API_KEY%" ^
    -e FREEDCAMP_API_SECRET="%FREEDCAMP_API_SECRET%" ^
    freedcamp-mcp:latest
