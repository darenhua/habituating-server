"""
Shared data models and constants for Temporal course sync workflow.

This module contains the data structures used throughout the workflow
and activity definitions for course synchronization.
"""

from typing import List, Optional
from pydantic import BaseModel

COURSE_SYNC_TASK_QUEUE_NAME = "COURSE_SYNC_TASK_QUEUE"


class SyncPipelineInput(BaseModel):
    """Input data for the sync pipeline workflow."""
    user_id: Optional[str] = None
    force_refresh: bool = False
    course_ids: Optional[List[str]] = None


class JobSyncResult(BaseModel):
    """Result from creating sync jobs."""
    job_sync_ids: List[str]
    total_created: int


class ScrapeResult(BaseModel):
    """Result from scraping a single course."""
    job_sync_id: str
    nodes_scraped: int
    assignment_pages_found: int
    success: bool
    error_message: Optional[str] = None


class AssignmentResult(BaseModel):
    """Result from finding assignments."""
    job_sync_id: str
    assignments_found: int
    assignments_created: int
    success: bool
    error_message: Optional[str] = None


class DueDateResult(BaseModel):
    """Result from finding due dates."""
    job_sync_id: str
    due_dates_found: int
    due_dates_created: int
    assignments_updated: int
    success: bool
    error_message: Optional[str] = None


class SyncPipelineResult(BaseModel):
    """Complete result from the sync pipeline."""
    job_sync_ids: List[str]
    scrape_results: List[ScrapeResult]
    assignment_results: List[AssignmentResult]
    due_date_results: List[DueDateResult]
    total_success: bool
    total_errors: int
    duration_seconds: float