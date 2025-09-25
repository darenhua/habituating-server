"""
Simple Temporal worker for hello world workflow.

This worker handles the simple hello world workflow and activities.
Run this in a separate terminal before running the workflow client.

Usage:
    python temporal/run_worker_simple.py
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to the Python path (parent of temporal directory)
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from temporalio.client import Client
from temporalio.worker import Worker
from temporal.simple.simple_activities import SimpleActivities
from temporal.simple.simple_workflows import SimpleHelloWorldWorkflow
from temporal.config import temporal_config


async def main() -> None:
    """Start the simple Temporal worker."""
    print(f"🚀 Starting simple hello world worker")
    print(f"Connecting to Temporal at {temporal_config.host}")
    
    # Connect to Temporal
    client: Client = await Client.connect(
        temporal_config.host, 
        namespace=temporal_config.namespace
    )
    
    print(f"✅ Connected to Temporal server")
    
    # Initialize activities
    activities = SimpleActivities()
    
    print(f"🔄 Starting worker for task queue: HELLO_WORLD_TASK_QUEUE")
    
    # Create and run worker
    worker: Worker = Worker(
        client,
        task_queue="HELLO_WORLD_TASK_QUEUE",
        workflows=[SimpleHelloWorldWorkflow],
        activities=[
            activities.say_hello,
            activities.count_letters,
            activities.create_summary,
        ],
    )
    
    print("🎯 Simple worker started!")
    print("   • Workflow: SimpleHelloWorldWorkflow")
    print("   • Activities: say_hello, count_letters, create_summary")
    print("   • Task Queue: HELLO_WORLD_TASK_QUEUE")
    print("\nPress Ctrl+C to stop the worker")
    
    try:
        await worker.run()
    except KeyboardInterrupt:
        print("\n🛑 Worker stopped by user")
    except Exception as e:
        print(f"❌ Worker failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())