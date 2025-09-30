"""
Temporal activities for course synchronization workflow.

Activities directly call the service classes instead of making HTTP requests,
wrapping them with Temporal's retry and error handling capabilities.
"""

import asyncio
import os
import json
from typing import List, Dict, Any
from datetime import datetime
from temporalio import activity
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

from ..shared import JobSyncResult, ScrapeResult, AssignmentResult, DueDateResult
from services.scraper_v2 import ScraperV2
from services.assignment_extractor import AssignmentExtractor
from services.due_date_finder import DueDateFinder


class CourseSyncActivities:
    """Activities for course synchronization operations."""

    def __init__(self):
        """Initialize the activities with Supabase client."""
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_ANON_KEY")

        if not supabase_url or not supabase_key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_ANON_KEY environment variables are required"
            )

        self.supabase: Client = create_client(supabase_url, supabase_key)

    @activity.defn
    async def create_sync_jobs(self, user_id: str) -> JobSyncResult:
        """
        Create sync course jobs and return job sync IDs.

        Creates job_sync_group and job_syncs directly in database.
        """
        try:
            print("HELLO WORLD", user_id)
            # Create job sync group
            job_sync_group_data = {
                "user_id": user_id,
                "created_at": datetime.now().isoformat(),
            }

            group_result = (
                self.supabase.table("job_sync_groups")
                .insert(job_sync_group_data)
                .execute()
            )

            if not group_result.data:
                raise Exception("Failed to create job sync group")

            group_id = group_result.data[0]["id"]
            activity.logger.info(f"Created job sync group: {group_id}")

            # Get user's courses first
            user_courses_result = (
                self.supabase.table("user_courses")
                .select("course_id")
                .eq("user_id", user_id)
                .execute()
            )

            if not user_courses_result.data:
                activity.logger.warning(f"No courses found for user {user_id}")
                return JobSyncResult(
                    job_sync_group_id=group_id, job_sync_ids=[], total_created=0
                )

            course_ids = [uc["course_id"] for uc in user_courses_result.data]

            # Get sources for user's courses only
            sources_result = (
                self.supabase.table("sources")
                .select("*")
                .in_("course_id", course_ids)
                .execute()
            )

            if not sources_result.data:
                activity.logger.warning(
                    f"No sources found for user {user_id}'s courses"
                )
                return JobSyncResult(
                    job_sync_group_id=group_id, job_sync_ids=[], total_created=0
                )

            # Create job sync for each source
            job_sync_ids = []

            for source in sources_result.data:
                job_sync_data = {
                    "job_sync_group_id": group_id,
                    "course_id": source["course_id"],
                    "source_id": source["id"],
                    "created_at": datetime.now().isoformat(),
                }

                sync_result = (
                    self.supabase.table("job_syncs").insert(job_sync_data).execute()
                )

                if sync_result.data:
                    job_sync_ids.append(sync_result.data[0]["id"])

            activity.logger.info(
                f"Created {len(job_sync_ids)} job syncs: {job_sync_ids}"
            )

            return JobSyncResult(
                job_sync_group_id=group_id,
                job_sync_ids=job_sync_ids,
                total_created=len(job_sync_ids),
            )

        except Exception as e:
            activity.logger.exception("Failed to create sync jobs")
            raise

    @activity.defn
    async def scrape_course(self, job_sync_id: str) -> ScrapeResult:
        """
        Scrape a single course using ScraperV2 service.

        Args:
            job_sync_id: The ID of the job sync to scrape

        Returns:
            ScrapeResult with scraping details
        """
        try:
            # Get job sync details
            job_sync_result = (
                self.supabase.table("job_syncs")
                .select("*")
                .eq("id", job_sync_id)
                .execute()
            )

            if not job_sync_result.data:
                raise Exception(f"Job sync {job_sync_id} not found")

            job_sync = job_sync_result.data[0]
            source_id = job_sync["source_id"]

            # Get source URL from sources table
            source_result = (
                self.supabase.table("sources")
                .select("url")
                .eq("id", source_id)
                .execute()
            )

            if not source_result.data:
                raise Exception(f"Source {source_id} not found")

            source_url = source_result.data[0]["url"]

            # Get previous scraped tree from same source for change detection
            previous_tree = None
            previous_sync_result = (
                self.supabase.table("job_syncs")
                .select("scraped_tree")
                .eq("source_id", source_id)
                .neq("id", job_sync_id)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )

            if (
                previous_sync_result.data
                and previous_sync_result.data[0]["scraped_tree"]
            ):
                previous_tree = previous_sync_result.data[0]["scraped_tree"]
                activity.logger.info(
                    f"Found previous tree for change detection from source: {source_url}"
                )

            # Get user_id from job_sync_groups to find cookies
            group_id = job_sync["job_sync_group_id"]
            group_result = (
                self.supabase.table("job_sync_groups")
                .select("user_id")
                .eq("id", group_id)
                .execute()
            )

            cookies = []
            if group_result.data and group_result.data[0]["user_id"]:
                user_id = group_result.data[0]["user_id"]

                # Get cookies from user_auth_details table
                cookies_result = (
                    self.supabase.table("user_auth_details")
                    .select("cookies")
                    .eq("user_id", user_id)
                    .execute()
                )
                print("TESTING", cookies_result.data)

                if cookies_result.data and cookies_result.data[0]["cookies"]:
                    cookies = cookies_result.data[0]["cookies"]
                    print("TESTING", cookies)

            # Initialize scraper and scrape
            scraper = ScraperV2(supabase_client=self.supabase, job_sync_id=job_sync_id)

            scraped_tree = await scraper.scrape_course_with_comparison(
                source_url=source_url, cookies=cookies, previous_tree=previous_tree
            )

            # Count nodes for metrics
            nodes_scraped = self._count_tree_nodes(scraped_tree)

            # Save scraped tree to database
            self.supabase.table("job_syncs").update({"scraped_tree": scraped_tree}).eq(
                "id", job_sync_id
            ).execute()

            activity.logger.info(f"Scraped job {job_sync_id}: {nodes_scraped} nodes")

            return ScrapeResult(
                job_sync_id=job_sync_id,
                nodes_scraped=nodes_scraped,
                assignment_pages_found=nodes_scraped,  # All pages can potentially have assignments
                success=True,
            )

        except Exception as e:
            activity.logger.exception(f"Failed to scrape course {job_sync_id}")
            return ScrapeResult(
                job_sync_id=job_sync_id,
                nodes_scraped=0,
                assignment_pages_found=0,
                success=False,
                error_message=str(e),
            )

    @activity.defn
    async def find_assignments(self, job_sync_id: str) -> AssignmentResult:
        """
        Find assignments for a course using AssignmentExtractor service.

        Args:
            job_sync_id: The ID of the job sync to find assignments for

        Returns:
            AssignmentResult with assignment details and list of assignment IDs
        """
        try:
            # Get job sync with scraped tree
            job_sync_result = (
                self.supabase.table("job_syncs")
                .select("*")
                .eq("id", job_sync_id)
                .execute()
            )

            if not job_sync_result.data:
                raise Exception(f"Job sync {job_sync_id} not found")

            job_sync = job_sync_result.data[0]
            scraped_tree = job_sync["scraped_tree"]

            if not scraped_tree:
                raise Exception(f"No scraped tree found for job sync {job_sync_id}")

            # Initialize assignment extractor
            extractor = AssignmentExtractor(supabase_client=self.supabase)

            # Extract assignments
            assignments = await extractor.extract_all_assignments(
                scraped_tree=scraped_tree, job_sync_id=job_sync_id
            )

            # Get all assignments for this course to return IDs
            course_id = job_sync["course_id"]
            course_assignments = (
                self.supabase.table("assignments")
                .select("id")
                .eq("course_id", course_id)
                .execute()
            )

            assignment_ids = (
                [a["id"] for a in course_assignments.data]
                if course_assignments.data
                else []
            )

            assignments_found = len(assignments)
            assignments_created = len([a for a in assignments if not a.repeated])

            activity.logger.info(
                f"Found assignments for job {job_sync_id}: {assignments_found} found, "
                f"{assignments_created} created"
            )

            # Store assignment IDs in result for next activity
            result = AssignmentResult(
                job_sync_id=job_sync_id,
                assignments_found=assignments_found,
                assignments_created=assignments_created,
                success=True,
            )

            # Add assignment_ids to the result (extend the model if needed)
            result.assignment_ids = assignment_ids

            return result

        except Exception as e:
            activity.logger.exception(f"Failed to find assignments for {job_sync_id}")
            return AssignmentResult(
                job_sync_id=job_sync_id,
                assignments_found=0,
                assignments_created=0,
                success=False,
                error_message=str(e),
            )

    @activity.defn
    async def find_due_dates(
        self, job_sync_id: str, assignment_ids: List[str] = None
    ) -> DueDateResult:
        """
        Find due dates for assignments using DueDateFinder service.

        Args:
            job_sync_id: The ID of the job sync to find due dates for
            assignment_ids: List of assignment IDs to find due dates for

        Returns:
            DueDateResult with due date details
        """
        try:
            # Get job sync with scraped tree
            job_sync_result = (
                self.supabase.table("job_syncs")
                .select("*")
                .eq("id", job_sync_id)
                .execute()
            )

            if not job_sync_result.data:
                raise Exception(f"Job sync {job_sync_id} not found")

            job_sync = job_sync_result.data[0]
            scraped_tree = job_sync["scraped_tree"]

            # Get assignments for this course if not provided
            if not assignment_ids:
                course_id = job_sync["course_id"]
                assignments_result = (
                    self.supabase.table("assignments")
                    .select("*")
                    .eq("course_id", course_id)
                    .execute()
                )

                assignments = assignments_result.data if assignments_result.data else []
            else:
                # Get assignments by IDs
                assignments_result = (
                    self.supabase.table("assignments")
                    .select("*")
                    .in_("id", assignment_ids)
                    .execute()
                )

                assignments = assignments_result.data if assignments_result.data else []

            if not assignments:
                activity.logger.warning(
                    f"No assignments found for job sync {job_sync_id}"
                )
                return DueDateResult(
                    job_sync_id=job_sync_id,
                    due_dates_found=0,
                    due_dates_created=0,
                    assignments_updated=0,
                    success=True,
                )

            # Initialize due date finder
            finder = DueDateFinder(supabase_client=self.supabase)

            # Find due dates
            due_dates = await finder.find_due_dates(
                scraped_tree=scraped_tree,
                assignments=assignments,
                job_sync_id=job_sync_id,
            )

            # Update assignments with due dates
            await finder.update_assignments_with_due_dates(due_dates, job_sync_id)

            due_dates_found = len(due_dates)
            due_dates_created = len([dd for dd in due_dates if dd.date])
            assignments_updated = len([dd for dd in due_dates if dd.date])

            activity.logger.info(
                f"Found due dates for job {job_sync_id}: {due_dates_found} found, "
                f"{due_dates_created} created, {assignments_updated} assignments updated"
            )

            return DueDateResult(
                job_sync_id=job_sync_id,
                due_dates_found=due_dates_found,
                due_dates_created=due_dates_created,
                assignments_updated=assignments_updated,
                success=True,
            )

        except Exception as e:
            activity.logger.exception(f"Failed to find due dates for {job_sync_id}")
            return DueDateResult(
                job_sync_id=job_sync_id,
                due_dates_found=0,
                due_dates_created=0,
                assignments_updated=0,
                success=False,
                error_message=str(e),
            )

    def _count_tree_nodes(self, tree: Dict) -> int:
        """Count total nodes in scraped tree."""
        count = 1  # Count current node
        for child in tree.get("children", []):
            count += self._count_tree_nodes(child)
        return count

    @activity.defn
    async def mark_job_sync_group_complete(self, job_sync_group_id: str) -> bool:
        """
        Mark a job sync group as completed by setting the completed_at timestamp.

        Args:
            job_sync_group_id: The ID of the job sync group to mark as complete

        Returns:
            True if successful, False otherwise
        """
        try:
            update_result = (
                self.supabase.table("job_sync_groups")
                .update({"completed_at": datetime.now().isoformat()})
                .eq("id", job_sync_group_id)
                .execute()
            )

            if update_result.data:
                activity.logger.info(
                    f"Marked job sync group {job_sync_group_id} as complete"
                )
                return True
            else:
                activity.logger.error(
                    f"Failed to mark job sync group {job_sync_group_id} as complete"
                )
                return False

        except Exception as e:
            activity.logger.exception(
                f"Error marking job sync group {job_sync_group_id} as complete"
            )
            return False
