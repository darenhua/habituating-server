"""
Simple workflow client for hello world demonstration.

This script runs the simple hello world workflow to demonstrate
basic Temporal workflow execution.

Usage:
    python temporal/run_workflow_simple.py [name]

If no name is provided, it defaults to "World".
"""

import asyncio
import sys
import traceback
from datetime import datetime
from pathlib import Path

# Add the project root to the Python path (parent of temporal directory)
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from temporalio.client import Client, WorkflowFailureError
from temporal.simple.simple_workflows import SimpleHelloWorldWorkflow
from temporal.config import temporal_config


async def main() -> None:
    """Run the simple hello world workflow."""
    # Get name from command line or use default
    name = sys.argv[1] if len(sys.argv) > 1 else "World"

    print(f"🚀 Starting simple hello world workflow for: {name}")
    print(f"Connecting to Temporal at {temporal_config.host}")

    try:
        # Connect to Temporal
        client: Client = await Client.connect(
            temporal_config.host,
            namespace=temporal_config.namespace
        )

        print(f"✅ Connected to Temporal server")

        # Generate unique workflow ID
        workflow_id = f"hello-world-{name.lower()}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        print(f"🔄 Starting workflow with ID: {workflow_id}")

        # Execute the workflow
        result = await client.execute_workflow(
            SimpleHelloWorldWorkflow.run,
            name,
            id=workflow_id,
            task_queue="HELLO_WORLD_TASK_QUEUE",  # Simple task queue name
        )

        print(f"\n🎉 Workflow completed successfully!")
        print(f"📊 Results:")
        print(f"  • Name: {result['name']}")
        print(f"  • Workflow complete: {result['workflow_complete']}")

    except WorkflowFailureError as e:
        print(f"\n❌ Workflow failed: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)
    except KeyboardInterrupt:
        print(f"\n🛑 Workflow interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
