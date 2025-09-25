"""
Temporal workflows for course synchronization.

This module defines the main workflow orchestration logic for course synchronization,
replacing the sequential script logic with a durable, fault-tolerant workflow.
"""

import asyncio
from datetime import timedelta
from typing import List

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from .activities import CourseSyncActivities
    from ..shared import (
        SyncPipelineInput, 
        SyncPipelineResult, 
        ScrapeResult, 
        AssignmentResult, 
        DueDateResult
    )


@workflow.defn
class CourseSyncWorkflow:
    """
    Main workflow for course synchronization pipeline.
    
    This workflow orchestrates the course sync process:
    1. Create sync jobs for all user courses
    2. Scrape all courses in parallel
    3. Find assignments for all courses in parallel  
    4. Find due dates for all courses in parallel
    """

    @workflow.run
    async def run(self, input_data: SyncPipelineInput) -> SyncPipelineResult:
        """
        Execute the complete course sync pipeline.
        
        Args:
            input_data: Pipeline input configuration
            
        Returns:
            SyncPipelineResult with complete pipeline results
        """
        start_time = workflow.now()
        
        workflow.logger.info("Starting course sync pipeline")
        
        # Configure retry policy for activities
        retry_policy = RetryPolicy(
            maximum_attempts=3,
            maximum_interval=timedelta(seconds=60),
            initial_interval=timedelta(seconds=1),
            backoff_coefficient=2.0,
            non_retryable_error_types=["ValueError", "AuthenticationError"],
        )

        try:
            # Step 1: Create sync jobs
            workflow.logger.info("Step 1: Creating sync jobs")
            job_sync_result = await workflow.execute_activity_method(
                CourseSyncActivities.create_sync_jobs,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry_policy,
            )
            
            job_sync_ids = job_sync_result.job_sync_ids
            
            if not job_sync_ids:
                workflow.logger.warning("No job syncs created. Ending pipeline.")
                return SyncPipelineResult(
                    job_sync_ids=[],
                    scrape_results=[],
                    assignment_results=[],
                    due_date_results=[],
                    total_success=True,
                    total_errors=0,
                    duration_seconds=(workflow.now() - start_time).total_seconds()
                )

            workflow.logger.info(f"Created {len(job_sync_ids)} job syncs")

            # Step 2-3: Scrape courses in parallel
            workflow.logger.info("Steps 2-3: Scraping courses in parallel")
            scrape_results = await self._execute_scraping_activities(
                job_sync_ids, retry_policy
            )

            # Step 4-5: Find assignments in parallel
            workflow.logger.info("Steps 4-5: Finding assignments in parallel")
            assignment_results = await self._execute_assignment_activities(
                job_sync_ids, retry_policy
            )

            # Step 6-7: Find due dates in parallel
            workflow.logger.info("Steps 6-7: Finding due dates in parallel")
            due_date_results = await self._execute_due_date_activities(
                job_sync_ids, retry_policy
            )

            # Calculate final results
            total_errors = self._count_errors(scrape_results, assignment_results, due_date_results)
            total_success = total_errors == 0
            duration_seconds = (workflow.now() - start_time).total_seconds()

            workflow.logger.info(
                f"Pipeline completed! Success: {total_success}, "
                f"Errors: {total_errors}, Duration: {duration_seconds:.2f}s"
            )

            return SyncPipelineResult(
                job_sync_ids=job_sync_ids,
                scrape_results=scrape_results,
                assignment_results=assignment_results,
                due_date_results=due_date_results,
                total_success=total_success,
                total_errors=total_errors,
                duration_seconds=duration_seconds
            )

        except Exception as e:
            workflow.logger.error(f"Pipeline failed with error: {e}")
            raise

    async def _execute_scraping_activities(
        self, 
        job_sync_ids: List[str], 
        retry_policy: RetryPolicy
    ) -> List[ScrapeResult]:
        """Execute scraping activities in parallel for all job sync IDs."""
        tasks = []
        
        for job_sync_id in job_sync_ids:
            task = workflow.execute_activity_method(
                CourseSyncActivities.scrape_course,
                job_sync_id,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=retry_policy,
            )
            tasks.append(task)
        
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            scrape_results = []
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    workflow.logger.error(f"Scrape failed for {job_sync_ids[i]}: {result}")
                    scrape_results.append(ScrapeResult(
                        job_sync_id=job_sync_ids[i],
                        nodes_scraped=0,
                        assignment_pages_found=0,
                        success=False,
                        error_message=str(result)
                    ))
                else:
                    scrape_results.append(result)
            
            successful_scrapes = sum(1 for r in scrape_results if r.success)
            workflow.logger.info(
                f"Scraping completed: {successful_scrapes}/{len(job_sync_ids)} successful"
            )
            
            return scrape_results
            
        except Exception as e:
            workflow.logger.error(f"Scraping phase failed: {e}")
            raise

    async def _execute_assignment_activities(
        self, 
        job_sync_ids: List[str], 
        retry_policy: RetryPolicy
    ) -> List[AssignmentResult]:
        """Execute assignment finding activities in parallel for all job sync IDs."""
        tasks = []
        
        for job_sync_id in job_sync_ids:
            task = workflow.execute_activity_method(
                CourseSyncActivities.find_assignments,
                job_sync_id,
                start_to_close_timeout=timedelta(minutes=3),
                retry_policy=retry_policy,
            )
            tasks.append(task)
        
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            assignment_results = []
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    workflow.logger.error(f"Assignment finding failed for {job_sync_ids[i]}: {result}")
                    assignment_results.append(AssignmentResult(
                        job_sync_id=job_sync_ids[i],
                        assignments_found=0,
                        assignments_created=0,
                        success=False,
                        error_message=str(result)
                    ))
                else:
                    assignment_results.append(result)
            
            successful_assignments = sum(1 for r in assignment_results if r.success)
            workflow.logger.info(
                f"Assignment finding completed: {successful_assignments}/{len(job_sync_ids)} successful"
            )
            
            return assignment_results
            
        except Exception as e:
            workflow.logger.error(f"Assignment finding phase failed: {e}")
            raise

    async def _execute_due_date_activities(
        self, 
        job_sync_ids: List[str], 
        retry_policy: RetryPolicy
    ) -> List[DueDateResult]:
        """Execute due date finding activities in parallel for all job sync IDs."""
        tasks = []
        
        for job_sync_id in job_sync_ids:
            task = workflow.execute_activity_method(
                CourseSyncActivities.find_due_dates,
                job_sync_id,
                start_to_close_timeout=timedelta(minutes=3),
                retry_policy=retry_policy,
            )
            tasks.append(task)
        
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            due_date_results = []
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    workflow.logger.error(f"Due date finding failed for {job_sync_ids[i]}: {result}")
                    due_date_results.append(DueDateResult(
                        job_sync_id=job_sync_ids[i],
                        due_dates_found=0,
                        due_dates_created=0,
                        assignments_updated=0,
                        success=False,
                        error_message=str(result)
                    ))
                else:
                    due_date_results.append(result)
            
            successful_due_dates = sum(1 for r in due_date_results if r.success)
            workflow.logger.info(
                f"Due date finding completed: {successful_due_dates}/{len(job_sync_ids)} successful"
            )
            
            return due_date_results
            
        except Exception as e:
            workflow.logger.error(f"Due date finding phase failed: {e}")
            raise

    def _count_errors(
        self, 
        scrape_results: List[ScrapeResult], 
        assignment_results: List[AssignmentResult], 
        due_date_results: List[DueDateResult]
    ) -> int:
        """Count total number of errors across all phases."""
        total_errors = 0
        
        total_errors += sum(1 for r in scrape_results if not r.success)
        total_errors += sum(1 for r in assignment_results if not r.success)  
        total_errors += sum(1 for r in due_date_results if not r.success)
        
        return total_errors