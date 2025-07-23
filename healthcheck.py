#!/usr/bin/env python3
"""
Health check script for Freedcamp MCP Server
Used by Docker to verify the container is healthy
"""

import sys
import os
import asyncio
from freedcamp_mcp import FreedcampConfig, FreedcampMCP

async def health_check():
    """Perform a simple health check"""
    try:
        # Check if environment variables are set
        api_key = os.getenv("FREEDCAMP_API_KEY", "")
        api_secret = os.getenv("FREEDCAMP_API_SECRET", "")
        
        if not api_key or not api_secret:
            print("ERROR: Missing API credentials")
            return False
        
        # Try to initialize the MCP server
        config = FreedcampConfig(api_key=api_key, api_secret=api_secret)
        mcp = FreedcampMCP(config)
        
        # Try a simple API call (get users is usually fast)
        users = await mcp.get_all_users()
        
        if isinstance(users, list):
            print(f"OK: Connected to Freedcamp API, found {len(users)} users")
            return True
        else:
            print("ERROR: Unexpected response from API")
            return False
            
    except Exception as e:
        print(f"ERROR: Health check failed - {str(e)}")
        return False
    finally:
        if 'mcp' in locals():
            await mcp.client.aclose()

if __name__ == "__main__":
    # Run the health check
    success = asyncio.run(health_check())
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)
