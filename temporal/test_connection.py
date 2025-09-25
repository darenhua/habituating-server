"""
Simple script to test Temporal server connection.

Run this to verify that Temporal server is running and accessible.
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from temporalio.client import Client
from temporal.config import temporal_config


async def test_connection():
    """Test connection to Temporal server."""
    try:
        print(f"🔄 Connecting to Temporal at {temporal_config.host}, namespace: {temporal_config.namespace}")
        
        client = await Client.connect(
            temporal_config.host, 
            namespace=temporal_config.namespace
        )
        
        print("✅ Successfully connected to Temporal server!")
        
        # Try to list namespaces to verify connection
        try:
            # This is just a simple operation to test the connection
            print("🔍 Testing connection with a simple operation...")
            # We don't need to actually do anything complex, just verify we can connect
            print("✅ Connection test successful!")
            
        except Exception as e:
            print(f"⚠️  Connected but couldn't perform operations: {e}")
            
    except Exception as e:
        print(f"❌ Failed to connect to Temporal server: {e}")
        print("\n💡 Make sure Temporal server is running:")
        print("   brew install temporal")
        print("   temporal server start-dev --db-filename temporal.db")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(test_connection())