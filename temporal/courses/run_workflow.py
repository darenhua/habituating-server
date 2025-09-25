"""
Client to start course synchronization workflows.

This script replaces the run-sync.py script and triggers the Temporal workflow
instead of making direct HTTP calls.

Usage:
    python temporal/run_workflow.py

Environment Variables:
    TEMPORAL_HOST: Temporal server host (default: localhost:7233)
    TEMPORAL_NAMESPACE: Temporal namespace (default: default)
"""

import asyncio
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

# Add the project root to the Python path so we can import temporal modules (parent of temporal directory)
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from temporalio.client import Client, WorkflowFailureError

from temporal.courses.workflows import CourseSyncWorkflow
from temporal.shared import COURSE_SYNC_TASK_QUEUE_NAME, SyncPipelineInput


async def main() -> None:
    """Start the course sync workflow."""
    # Get configuration from environment
    temporal_host = os.getenv("TEMPORAL_HOST", "localhost:7233")
    temporal_namespace = os.getenv("TEMPORAL_NAMESPACE", "default")
    
    print(f"🚀 Starting course sync pipeline...")
    print(f"Connecting to Temporal at {temporal_host}, namespace: {temporal_namespace}")
    
    # Connect to Temporal
    client: Client = await Client.connect(
        temporal_host, 
        namespace=temporal_namespace
    )
    
    print(f"✅ Connected to Temporal server")
    
    # Create workflow input
    input_data = SyncPipelineInput(
        force_refresh=False,  # Can be made configurable via CLI args
        course_ids=None       # None means sync all courses for user
    )
    
    # Generate unique workflow ID
    workflow_id = f"course-sync-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    print(f"🔄 Starting workflow with ID: {workflow_id}")
    
    try:
        # Execute the workflow
        result = await client.execute_workflow(
            CourseSyncWorkflow.run,
            input_data,
            id=workflow_id,
            task_queue=COURSE_SYNC_TASK_QUEUE_NAME,
        )
        
        print("\n🎉 Course sync pipeline completed successfully!")
        print(f"📊 Results:")
        print(f"  • Job syncs created: {len(result.job_sync_ids)}")
        print(f"  • Courses scraped: {len([r for r in result.scrape_results if r.success])}/{len(result.scrape_results)}")
        print(f"  • Assignments found: {len([r for r in result.assignment_results if r.success])}/{len(result.assignment_results)}")
        print(f"  • Due dates found: {len([r for r in result.due_date_results if r.success])}/{len(result.due_date_results)}")
        print(f"  • Total errors: {result.total_errors}")
        print(f"  • Duration: {result.duration_seconds:.2f} seconds")
        
        # Show error details if any
        if result.total_errors > 0:
            print(f"\n⚠️  Errors encountered:")
            
            for scrape_result in result.scrape_results:
                if not scrape_result.success:
                    print(f"  • Scrape failed for {scrape_result.job_sync_id}: {scrape_result.error_message}")
            
            for assignment_result in result.assignment_results:
                if not assignment_result.success:
                    print(f"  • Assignment finding failed for {assignment_result.job_sync_id}: {assignment_result.error_message}")
            
            for due_date_result in result.due_date_results:
                if not due_date_result.success:
                    print(f"  • Due date finding failed for {due_date_result.job_sync_id}: {due_date_result.error_message}")
        
        # Show successful stats
        if result.total_errors == 0:
            total_nodes = sum(r.nodes_scraped for r in result.scrape_results)
            total_assignments = sum(r.assignments_created for r in result.assignment_results)
            total_due_dates = sum(r.due_dates_created for r in result.due_date_results)
            
            print(f"\n📈 Summary:")
            print(f"  • Total nodes scraped: {total_nodes}")
            print(f"  • Total assignments created: {total_assignments}")
            print(f"  • Total due dates created: {total_due_dates}")

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