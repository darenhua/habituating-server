"""
Simple hello world workflow for Temporal demonstration.

This workflow shows the basic pattern of Temporal workflow orchestration
without the complexity of the course sync implementation.
"""

from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from .simple_activities import SimpleActivities


@workflow.defn
class SimpleHelloWorldWorkflow:
    """
    Simple workflow that demonstrates basic Temporal concepts.

    This workflow:
    1. Says hello to a person
    2. Counts letters in their name
    3. Creates a summary of the results
    """

    @workflow.run
    async def run(self, name: str) -> dict:
        """
        Execute the simple hello world workflow.

        Args:
            name: The name to greet

        Returns:
            Dictionary with workflow results
        """
        workflow.logger.info(f"Starting hello world workflow for: {name}")

        # Configure retry policy for activities
        retry_policy = RetryPolicy(
            maximum_attempts=3,
            maximum_interval=timedelta(seconds=10),
            initial_interval=timedelta(seconds=1),
            backoff_coefficient=2.0
        )

        # Step 1: Say hello
        workflow.logger.info("Step 1: Saying hello")
        greeting = await workflow.execute_activity(
            "say_hello",
            name,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=retry_policy
        )

        # Step 2: Count letters in the name
        workflow.logger.info("Step 2: Counting letters")
        letter_count = await workflow.execute_activity(
            "count_letters",
            name,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=retry_policy
        )

        # Step 3: Create summary
        workflow.logger.info("Step 3: Creating summary")
        summary = await workflow.execute_activity(
            "create_summary",
            letter_count,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=retry_policy
        )

        workflow.logger.info(f"Workflow completed successfully for {name}")
        return summary
