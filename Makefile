.PHONY: help build run test clean logs shell push health dev

# Default target
help:
	@echo "Freedcamp MCP Docker Commands:"
	@echo "  make build    - Build the Docker image"
	@echo "  make run      - Run the MCP server in Docker"
	@echo "  make test     - Run the test script in Docker"
	@echo "  make health   - Check container health"
	@echo "  make logs     - Show container logs"
	@echo "  make shell    - Open a shell in the container"
	@echo "  make clean    - Remove containers and images"
	@echo "  make push     - Push image to registry (configure REGISTRY first)"

# Build the Docker image
build:
	docker build -t freedcamp-mcp:latest .

# Run the MCP server
run: build
	docker run --rm -i \
		--env-file .env \
		freedcamp-mcp:latest

# Run tests in Docker
test: build
	docker run --rm \
		--env-file .env \
		-v $(PWD)/test_freedcamp.py:/app/test_freedcamp.py:ro \
		freedcamp-mcp:latest python test_freedcamp.py

# Check container health
health: build
	docker run --rm \
		--env-file .env \
		freedcamp-mcp:latest python healthcheck.py

# Show logs (when using docker-compose)
logs:
	docker-compose logs -f

# Open a shell in the container
shell: build
	docker run --rm -it \
		--env-file .env \
		--entrypoint /bin/bash \
		freedcamp-mcp:latest

# Clean up Docker resources
clean:
	docker-compose down -v
	docker rmi freedcamp-mcp:latest || true
	docker system prune -f

# Push to registry (configure REGISTRY variable)
REGISTRY ?= docker.io/yourusername
push: build
	docker tag freedcamp-mcp:latest $(REGISTRY)/freedcamp-mcp:latest
	docker push $(REGISTRY)/freedcamp-mcp:latest

# Development mode with live code reload
dev: build
	docker run --rm -i \
		--env-file .env \
		-v $(PWD)/freedcamp_mcp.py:/app/freedcamp_mcp.py:ro \
		freedcamp-mcp:latest

# Check if .env file exists
check-env:
	@if [ ! -f .env ]; then \
		echo "Error: .env file not found. Copy .env.example to .env and add your credentials."; \
		exit 1; \
	fi

# Run with environment check
safe-run: check-env run
