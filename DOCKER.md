# Docker Setup for Freedcamp MCP Server

This guide explains how to run the Freedcamp MCP server using Docker.

## Prerequisites

- Docker installed on your system
- Docker Compose (optional, for easier management)
- Freedcamp API credentials

## Quick Start

### Option 1: Using Docker Compose (Recommended)

1. Create a `.env` file with your credentials:
   ```bash
   FREEDCAMP_API_KEY=your_api_key_here
   FREEDCAMP_API_SECRET=your_api_secret_here
   ```

2. Build and run:
   ```bash
   docker-compose up --build
   ```

### Option 2: Using Docker directly

1. Build the image:
   ```bash
   docker build -t freedcamp-mcp:latest .
   ```

2. Run the container:
   ```bash
   docker run --rm -i \
     -e FREEDCAMP_API_KEY="your_api_key" \
     -e FREEDCAMP_API_SECRET="your_api_secret" \
     freedcamp-mcp:latest
   ```

## Integration with Claude Desktop

### macOS/Linux Configuration

1. Make the wrapper script executable:
   ```bash
   chmod +x run-freedcamp-mcp.sh
   ```

2. Add to Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):
   ```json
   {
     "mcpServers": {
       "freedcamp": {
         "command": "/path/to/run-freedcamp-mcp.sh",
         "env": {
           "FREEDCAMP_API_KEY": "your_api_key",
           "FREEDCAMP_API_SECRET": "your_api_secret"
         }
       }
     }
   }
   ```

### Windows Configuration

1. Add to Claude Desktop config (`%APPDATA%\Claude\claude_desktop_config.json`):
   ```json
   {
     "mcpServers": {
       "freedcamp": {
         "command": "C:\\path\\to\\run-freedcamp-mcp.bat",
         "env": {
           "FREEDCAMP_API_KEY": "your_api_key",
           "FREEDCAMP_API_SECRET": "your_api_secret"
         }
       }
     }
   }
   ```

## Docker Commands Reference

### Build the image:
```bash
docker build -t freedcamp-mcp:latest .
```

### Run interactively (for testing):
```bash
docker run --rm -it \
  -e FREEDCAMP_API_KEY="your_key" \
  -e FREEDCAMP_API_SECRET="your_secret" \
  freedcamp-mcp:latest
```

### Run with Docker Compose:
```bash
# Start in background
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Run with volume mounting (for development):
```bash
docker run --rm -i \
  -v $(pwd)/freedcamp_mcp.py:/app/freedcamp_mcp.py:ro \
  -e FREEDCAMP_API_KEY="your_key" \
  -e FREEDCAMP_API_SECRET="your_secret" \
  freedcamp-mcp:latest
```

## Advanced Configuration

### Using Docker Secrets (for production)

1. Create secrets:
   ```bash
   echo "your_api_key" | docker secret create freedcamp_api_key -
   echo "your_api_secret" | docker secret create freedcamp_api_secret -
   ```

2. Update docker-compose.yml to use secrets:
   ```yaml
   services:
     freedcamp-mcp:
       secrets:
         - freedcamp_api_key
         - freedcamp_api_secret
       environment:
         - FREEDCAMP_API_KEY_FILE=/run/secrets/freedcamp_api_key
         - FREEDCAMP_API_SECRET_FILE=/run/secrets/freedcamp_api_secret
   
   secrets:
     freedcamp_api_key:
       external: true
     freedcamp_api_secret:
       external: true
   ```

### Multi-stage Build (for smaller images)

The Dockerfile can be optimized with multi-stage builds:

```dockerfile
# Build stage
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY freedcamp_mcp.py .
ENV PATH=/root/.local/bin:$PATH
ENTRYPOINT ["python", "-u", "freedcamp_mcp.py"]
```

## Troubleshooting

### Container exits immediately
- Ensure you're running with `-i` flag for interactive mode
- Check logs: `docker logs freedcamp-mcp`

### Permission denied errors
- The wrapper scripts need execute permissions: `chmod +x run-freedcamp-mcp.sh`

### Can't connect to MCP server
- Verify Docker is running: `docker ps`
- Check if the image built successfully: `docker images | grep freedcamp-mcp`
- Test the container directly: `docker run --rm -it freedcamp-mcp:latest`

### Environment variables not working
- Verify they're set correctly: `docker run --rm freedcamp-mcp:latest env | grep FREEDCAMP`
- Check your .env file formatting (no spaces around `=`)

## Security Considerations

1. **Never commit `.env` files** with real credentials to version control
2. **Use Docker secrets** for production deployments
3. **Run as non-root user** (already configured in Dockerfile)
4. **Set resource limits** to prevent resource exhaustion
5. **Keep the image updated** with latest security patches

## Performance Optimization

The Docker setup includes:
- Small base image (python:3.11-slim)
- Layer caching for dependencies
- Resource limits in docker-compose.yml
- No unnecessary system packages
