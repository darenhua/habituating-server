"""
Temporal activities for course synchronization workflow.

Activities handle the actual HTTP requests to the existing FastAPI endpoints,
wrapping them with Temporal's retry and error handling capabilities.
"""

import asyncio
from typing import List, Dict, Any
import aiohttp
from temporalio import activity

from ..shared import JobSyncResult, ScrapeResult, AssignmentResult, DueDateResult
from ..config import course_sync_config


class CourseSyncActivities:
    """Activities for course synchronization operations."""

    def __init__(self):
        """Initialize the activities with configuration."""
        self.base_url = course_sync_config.base_url
        self.headers = course_sync_config.headers

    async def _make_request_with_retry(
        self, 
        session: aiohttp.ClientSession, 
        method: str, 
        url: str, 
        json_data: Dict = None
    ) -> Dict[str, Any]:
        """Make HTTP request with retry logic."""
        for attempt in range(course_sync_config.max_retries):
            try:
                async with session.request(
                    method, url, headers=self.headers, json=json_data
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        error_text = await response.text()
                        activity.logger.warning(
                            f"Request failed with status {response.status}: {error_text}"
                        )
                        if attempt == course_sync_config.max_retries - 1:
                            raise Exception(
                                f"Request failed after {course_sync_config.max_retries} attempts: {error_text}"
                            )
            except Exception as e:
                activity.logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt == course_sync_config.max_retries - 1:
                    raise
                await asyncio.sleep(course_sync_config.retry_delay * (attempt + 1))

    @activity.defn
    async def create_sync_jobs(self) -> JobSyncResult:
        """
        Create sync course jobs and return job sync IDs.
        
        Wraps the POST /sync-course endpoint.
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/sync-course"
                response = await self._make_request_with_retry(session, "POST", url)
                
                job_syncs = response.get("job_syncs", [])
                job_sync_ids = [job_sync["id"] for job_sync in job_syncs]
                
                activity.logger.info(f"Created {len(job_sync_ids)} job syncs: {job_sync_ids}")
                
                return JobSyncResult(
                    job_sync_ids=job_sync_ids,
                    total_created=len(job_sync_ids)
                )
                
        except Exception as e:
            activity.logger.exception("Failed to create sync jobs")
            raise

    @activity.defn
    async def scrape_course(self, job_sync_id: str) -> ScrapeResult:
        """
        Scrape a single course.
        
        Wraps the POST /sync-course/{job_sync_id}/scrape endpoint.
        
        Args:
            job_sync_id: The ID of the job sync to scrape
            
        Returns:
            ScrapeResult with scraping details
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/sync-course/{job_sync_id}/scrape"
                response = await self._make_request_with_retry(session, "POST", url)
                
                nodes_scraped = response.get("nodes_scraped", 0)
                assignment_pages_found = response.get("assignment_pages_found", 0)
                
                activity.logger.info(
                    f"Scraped job {job_sync_id}: {nodes_scraped} nodes, "
                    f"{assignment_pages_found} assignment pages"
                )
                
                return ScrapeResult(
                    job_sync_id=job_sync_id,
                    nodes_scraped=nodes_scraped,
                    assignment_pages_found=assignment_pages_found,
                    success=True
                )
                
        except Exception as e:
            activity.logger.exception(f"Failed to scrape course {job_sync_id}")
            return ScrapeResult(
                job_sync_id=job_sync_id,
                nodes_scraped=0,
                assignment_pages_found=0,
                success=False,
                error_message=str(e)
            )

    @activity.defn
    async def find_assignments(self, job_sync_id: str) -> AssignmentResult:
        """
        Find assignments for a course.
        
        Wraps the POST /sync-course/{job_sync_id}/assignments endpoint.
        
        Args:
            job_sync_id: The ID of the job sync to find assignments for
            
        Returns:
            AssignmentResult with assignment details
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/sync-course/{job_sync_id}/assignments"
                response = await self._make_request_with_retry(session, "POST", url)
                
                assignments_found = response.get("assignments_found", 0)
                assignments_created = response.get("assignments_created", 0)
                
                activity.logger.info(
                    f"Found assignments for job {job_sync_id}: {assignments_found} found, "
                    f"{assignments_created} created"
                )
                
                return AssignmentResult(
                    job_sync_id=job_sync_id,
                    assignments_found=assignments_found,
                    assignments_created=assignments_created,
                    success=True
                )
                
        except Exception as e:
            activity.logger.exception(f"Failed to find assignments for {job_sync_id}")
            return AssignmentResult(
                job_sync_id=job_sync_id,
                assignments_found=0,
                assignments_created=0,
                success=False,
                error_message=str(e)
            )

    @activity.defn
    async def find_due_dates(self, job_sync_id: str) -> DueDateResult:
        """
        Find due dates for a course.
        
        Wraps the POST /sync-course/{job_sync_id}/due-dates endpoint.
        
        Args:
            job_sync_id: The ID of the job sync to find due dates for
            
        Returns:
            DueDateResult with due date details
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/sync-course/{job_sync_id}/due-dates"
                response = await self._make_request_with_retry(session, "POST", url)
                
                due_dates_found = response.get("due_dates_found", 0)
                due_dates_created = response.get("due_dates_created", 0)
                assignments_updated = response.get("assignments_updated", 0)
                
                activity.logger.info(
                    f"Found due dates for job {job_sync_id}: {due_dates_found} found, "
                    f"{due_dates_created} created, {assignments_updated} assignments updated"
                )
                
                return DueDateResult(
                    job_sync_id=job_sync_id,
                    due_dates_found=due_dates_found,
                    due_dates_created=due_dates_created,
                    assignments_updated=assignments_updated,
                    success=True
                )
                
        except Exception as e:
            activity.logger.exception(f"Failed to find due dates for {job_sync_id}")
            return DueDateResult(
                job_sync_id=job_sync_id,
                due_dates_found=0,
                due_dates_created=0,
                assignments_updated=0,
                success=False,
                error_message=str(e)
            )