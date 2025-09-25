"""
Tests for course sync workflows.

These tests use Temporal's testing environment to test workflows in isolation
without requiring a running Temporal server.
"""

import uuid
import pytest
from temporalio.client import WorkflowFailureError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from temporal.activities import CourseSyncActivities
from temporal.workflows import CourseSyncWorkflow
from temporal.shared import SyncPipelineInput


@pytest.mark.asyncio
async def test_course_sync_workflow_success() -> None:
    """Test successful course sync workflow execution."""
    task_queue_name: str = str(uuid.uuid4())
    
    async with await WorkflowEnvironment.start_time_skipping() as env:
        input_data = SyncPipelineInput(
            force_refresh=False,
            course_ids=None
        )
        
        activities = CourseSyncActivities()
        
        async with Worker(
            env.client,
            task_queue=task_queue_name,
            workflows=[CourseSyncWorkflow],
            activities=[
                activities.create_sync_jobs,
                activities.scrape_course,
                activities.find_assignments,
                activities.find_due_dates,
            ],
        ):
            result = await env.client.execute_workflow(
                CourseSyncWorkflow.run,
                input_data,
                id=str(uuid.uuid4()),
                task_queue=task_queue_name,
            )
            
            # Verify result structure
            assert result is not None
            assert hasattr(result, 'job_sync_ids')
            assert hasattr(result, 'scrape_results')
            assert hasattr(result, 'assignment_results')
            assert hasattr(result, 'due_date_results')
            assert hasattr(result, 'total_success')
            assert hasattr(result, 'total_errors')
            assert hasattr(result, 'duration_seconds')
            
            # Check that duration is reasonable
            assert result.duration_seconds >= 0
            
            print(f"Test completed: {len(result.job_sync_ids)} job syncs processed")


@pytest.mark.asyncio
async def test_course_sync_workflow_with_custom_input() -> None:
    """Test course sync workflow with custom input parameters."""
    task_queue_name: str = str(uuid.uuid4())
    
    async with await WorkflowEnvironment.start_time_skipping() as env:
        input_data = SyncPipelineInput(
            force_refresh=True,
            course_ids=["test-course-1", "test-course-2"]
        )
        
        activities = CourseSyncActivities()
        
        async with Worker(
            env.client,
            task_queue=task_queue_name,
            workflows=[CourseSyncWorkflow],
            activities=[
                activities.create_sync_jobs,
                activities.scrape_course,
                activities.find_assignments,
                activities.find_due_dates,
            ],
        ):
            result = await env.client.execute_workflow(
                CourseSyncWorkflow.run,
                input_data,
                id=str(uuid.uuid4()),
                task_queue=task_queue_name,
            )
            
            # Verify the workflow completed
            assert result is not None
            print(f"Custom input test completed: {result.total_success}")


@pytest.mark.asyncio 
async def test_course_sync_workflow_no_jobs() -> None:
    """Test workflow behavior when no sync jobs are created."""
    task_queue_name: str = str(uuid.uuid4())
    
    # This test would require mocking the activities to return empty results
    # For now, it's a placeholder showing the testing pattern
    
    async with await WorkflowEnvironment.start_time_skipping() as env:
        input_data = SyncPipelineInput()
        
        activities = CourseSyncActivities()
        
        async with Worker(
            env.client,
            task_queue=task_queue_name,
            workflows=[CourseSyncWorkflow],
            activities=[
                activities.create_sync_jobs,
                activities.scrape_course,
                activities.find_assignments,
                activities.find_due_dates,
            ],
        ):
            result = await env.client.execute_workflow(
                CourseSyncWorkflow.run,
                input_data,
                id=str(uuid.uuid4()),
                task_queue=task_queue_name,
            )
            
            # Should handle empty job list gracefully
            assert result is not None
            print(f"No jobs test completed")


# Additional tests could include:
# - Testing individual activity failures
# - Testing partial failures
# - Testing timeout scenarios
# - Testing retry behavior
# - Mocking external HTTP calls for isolated testing