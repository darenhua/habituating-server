"""
Configuration management for Temporal course sync workflows.

Centralized configuration loading from environment variables with sensible defaults.
"""

import os
from datetime import timedelta
from typing import Dict, List
from pydantic import BaseModel, Field, validator
from temporalio.common import RetryPolicy
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class TemporalConfig(BaseModel):
    """Configuration for Temporal connection and workflows."""
    
    # Temporal server settings
    host: str = Field(default_factory=lambda: os.getenv("TEMPORAL_HOST", "localhost:7233"))
    namespace: str = Field(default_factory=lambda: os.getenv("TEMPORAL_NAMESPACE", "default"))
    
    # Activity timeout settings (in seconds, converted to timedelta when accessed)
    create_jobs_timeout_seconds: int = 30
    scrape_timeout_seconds: int = 300  # 5 minutes
    assignments_timeout_seconds: int = 180  # 3 minutes
    due_dates_timeout_seconds: int = 180  # 3 minutes
    
    # Workflow timeout (in seconds)
    workflow_execution_timeout_seconds: int = 7200  # 2 hours
    
    # Retry policy settings
    retry_initial_interval_seconds: int = 1
    retry_backoff_coefficient: float = 2.0
    retry_maximum_interval_seconds: int = 60
    retry_maximum_attempts: int = 3
    retry_non_retryable_error_types: List[str] = ["ValueError", "AuthenticationError"]
    
    @property
    def create_jobs_timeout(self) -> timedelta:
        return timedelta(seconds=self.create_jobs_timeout_seconds)
    
    @property
    def scrape_timeout(self) -> timedelta:
        return timedelta(seconds=self.scrape_timeout_seconds)
    
    @property
    def assignments_timeout(self) -> timedelta:
        return timedelta(seconds=self.assignments_timeout_seconds)
    
    @property
    def due_dates_timeout(self) -> timedelta:
        return timedelta(seconds=self.due_dates_timeout_seconds)
    
    @property
    def workflow_execution_timeout(self) -> timedelta:
        return timedelta(seconds=self.workflow_execution_timeout_seconds)
    
    @property
    def default_retry_policy(self) -> RetryPolicy:
        """Get the default retry policy for activities."""
        return RetryPolicy(
            initial_interval=timedelta(seconds=self.retry_initial_interval_seconds),
            backoff_coefficient=self.retry_backoff_coefficient,
            maximum_interval=timedelta(seconds=self.retry_maximum_interval_seconds),
            maximum_attempts=self.retry_maximum_attempts,
            non_retryable_error_types=self.retry_non_retryable_error_types
        )
    
    class Config:
        arbitrary_types_allowed = True


class CourseSyncConfig(BaseModel):
    """Configuration for course sync API calls."""
    
    base_url: str = Field(default_factory=lambda: os.getenv("BASE_URL", "http://localhost:8000"))
    auth_token: str = Field(default_factory=lambda: os.getenv("AUTH_TOKEN", ""))
    
    # HTTP request settings
    max_retries: int = 3
    retry_delay: float = 1.0
    request_timeout: int = 30
    
    @validator('auth_token')
    def validate_auth_token(cls, v):
        if not v:
            raise ValueError("AUTH_TOKEN environment variable is required")
        return v
    
    @property
    def headers(self) -> Dict[str, str]:
        """Get HTTP headers for API requests."""
        return {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json"
        }
    
    class Config:
        arbitrary_types_allowed = True


# Global configuration instances
temporal_config = TemporalConfig()
course_sync_config = CourseSyncConfig()