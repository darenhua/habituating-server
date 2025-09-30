"""
Temporal worker process for course synchronization.

This script starts a Temporal worker that can execute the course sync workflow
and activities. Run this in a separate process/terminal from the workflow client.

Usage:
    python temporal/run_worker.py

Environment Variables:
    TEMPORAL_HOST: Temporal server host (default: localhost:7233)
    TEMPORAL_NAMESPACE: Temporal namespace (default: default)
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from temporalio.client import Client
from temporalio.worker import Worker

from temporal.courses.activities import CourseSyncActivities
from temporal.courses.workflows import CourseSyncWorkflow
from temporal.shared import COURSE_SYNC_TASK_QUEUE_NAME


async def main() -> None:
    """Start the Temporal worker."""
    # Get configuration from environment
    temporal_host = os.getenv("TEMPORAL_HOST", "localhost:7233")
    temporal_namespace = os.getenv("TEMPORAL_NAMESPACE", "default")

    print(f"Connecting to Temporal at {temporal_host}, namespace: {temporal_namespace}")

    # Connect to Temporal
    client: Client = await Client.connect(temporal_host, namespace=temporal_namespace)

    print(f"Connected to Temporal server")

    # Initialize activities
    activities = CourseSyncActivities()

    print(f"Starting worker for task queue: {COURSE_SYNC_TASK_QUEUE_NAME}")

    # Create and run worker
    worker: Worker = Worker(
        client,
        task_queue=COURSE_SYNC_TASK_QUEUE_NAME,
        workflows=[CourseSyncWorkflow],
        activities=[
            activities.create_sync_jobs,
            activities.scrape_course,
            activities.find_assignments,
            activities.find_due_dates,
            activities.mark_job_sync_group_complete,
        ],
    )

    print("🚀 Course sync worker started!")
    print("Press Ctrl+C to stop the worker")

    try:
        await worker.run()
    except KeyboardInterrupt:
        print("\n🛑 Worker stopped by user")
    except Exception as e:
        print(f"❌ Worker failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
