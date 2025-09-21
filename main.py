from enum import Enum
from math import e
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import uvicorn
from supabase import create_client, Client
import os
from typing import Optional
from entities.fastapi.schema_public_latest import (
    Users,
    Courses,
    Sources,
    UserAssignmentsInsert,
)
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import List
from pydantic import UUID4
import datetime
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import sys

sys.path.append("./test")
from test import Scraper
from unique import find_unique_assignments, Assignment
from due_dates import find_due_dates, get_assignments_from_db, select_best_due_date

load_dotenv()

app = FastAPI()

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Users:
    """
    Dependency to get the current user from bearer token.

    1. Extract access token from bearer authorization header
    2. Use Supabase SDK to get session from token
    3. Get auth user ID from session
    4. Fetch user from public.users table using auth_id
    """
    token = credentials.credentials

    try:
        # Get user session from Supabase using the access token
        user_response = supabase.auth.get_user(token)

        if not user_response or not user_response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        auth_user_id = user_response.user.id

        # Fetch user from public.users table using auth_id
        result = (
            supabase.table("users")
            .select("*")
            .eq("auth_id", auth_user_id)
            .single()
            .execute()
        )

        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found in database",
            )

        # Convert the response to Users model
        user = Users(**result.data)
        return user

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


colors = ["purple", "pink", "blue", "green", "yellow", "orange", "brown"]


class JobSyncGroupStatus(Enum):
    STARTED = "STARTED"
    SCRAPED_TREE = "SCRAPED_TREE"
    UNIQUE_ASSIGNMENTS = "UNIQUE_ASSIGNMENTS"
    ASSIGNMENT_DATES = "ASSIGNMENT_DATES"
    COMPLETED = "COMPLETED"


class SourceInfo(BaseModel):
    """Source information with sync status."""

    url: str | None = None
    synced: bool


class CourseWithColor(BaseModel):
    """Course model with color attribute."""

    id: UUID4
    created_at: datetime.datetime
    title: str | None = None
    source: List[SourceInfo] = []
    color: str


class CourseInfo(BaseModel):
    """Course information without source data."""

    id: UUID4
    created_at: datetime.datetime
    title: str | None = None
    color: str


class AssignmentResponse(BaseModel):
    """Response model for assignment data."""

    assignment_id: UUID4
    title: str | None
    due_date: datetime.datetime | None
    conflicting_due_date_count: int
    course: CourseInfo


class DueDate(BaseModel):
    """Due date model for assignment due dates response."""

    source_url: str | None
    title: str | None
    date: str | None
    selected: bool


class AssignmentDueDatesResponse(BaseModel):
    """Response model for assignment due dates with pagination."""

    assignment_id: UUID4
    data: List[DueDate]
    hasMore: bool
    total: int


class CourseSyncRequest(BaseModel):
    """Request model for course sync endpoint."""

    course_ids: List[UUID4]


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/me")
async def get_me(current_user: Users = Depends(get_current_user)):
    """Get current user information."""
    return current_user


@app.get("/protected")
async def protected_route(current_user: Users = Depends(get_current_user)):
    """Example protected endpoint that requires authentication."""
    return {
        "message": f"Hello {current_user.full_name or current_user.email}!",
        "user_id": str(current_user.id),
        "email": current_user.email,
    }


@app.get("/courses", response_model=List[CourseWithColor])
async def get_user_courses(current_user: Users = Depends(get_current_user)):
    """Get all courses with their sources for the logged-in user."""
    try:
        # Query to get all courses for the user with their sources and auth details
        # Join user_courses -> courses -> sources -> user_auth_details
        result = (
            supabase.table("user_courses")
            .select("*, courses(*, sources(*, user_auth_details(*)))")
            .eq("user_id", str(current_user.id))
            .execute()
        )

        if not result.data:
            return []

        # Extract unique courses and assign colors
        courses_dict = {}
        for user_course in result.data:
            course_data = user_course.get("courses")
            if course_data and course_data["id"] not in courses_dict:
                courses_dict[course_data["id"]] = course_data

        # Convert to list and sort by created_at
        courses_list = sorted(courses_dict.values(), key=lambda x: x["created_at"])

        # Create CourseWithColor objects with color assignment
        courses_with_colors = []
        for index, course_data in enumerate(courses_list):
            # Assign color based on order (oldest = purple, etc.)
            color = colors[index % len(colors)]

            # Process sources to create SourceInfo array
            source_info_list = []
            sources = course_data.get("sources", [])

            for source in sources:
                # Get the URL from the source
                url = source.get("url")

                # Check if any user_auth_details exist and are in sync
                user_auth_details = source.get("user_auth_details", [])
                synced = False
                if user_auth_details:
                    # Check if any auth detail is in sync
                    synced = any(
                        auth.get("in_sync", False) for auth in user_auth_details
                    )

                # Create SourceInfo object
                source_info = SourceInfo(url=url, synced=synced)
                source_info_list.append(source_info)

            # Create CourseWithColor instance with the extracted data
            course_with_color = CourseWithColor(
                id=course_data["id"],
                created_at=course_data["created_at"],
                title=course_data.get("title"),
                source=source_info_list,
                color=color,
            )
            courses_with_colors.append(course_with_color)

        return courses_with_colors

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch courses: {str(e)}",
        )


def get_user_course_ids(user_id: str) -> List[str]:
    """Get all course IDs for a user."""
    result = (
        supabase.table("user_courses")
        .select("course_id")
        .eq("user_id", user_id)
        .execute()
    )
    return [uc["course_id"] for uc in result.data] if result.data else []


def fetch_assignments_for_courses(course_ids: List[str]) -> List[dict]:
    """Fetch all assignments for given course IDs with their due dates and course info."""
    if not course_ids:
        return []

    result = (
        supabase.table("assignments")
        .select("*, due_dates!chosen_due_date_id!left(*), courses(*)")
        .in_("course_id", course_ids)
        .execute()
    )
    return result.data if result.data else []


def fetch_user_assignments(user_id: str) -> dict:
    """Fetch all user assignments for a user and return as a map."""
    result = (
        supabase.table("user_assignments")
        .select("*, due_dates!chosen_due_date_id!left(*), assignments!assignment_id(*)")
        .eq("user_id", user_id)
        .execute()
    )

    user_assignments_map = {}
    if result.data:
        for ua in result.data:
            user_assignments_map[ua["assignment_id"]] = ua
    return user_assignments_map


def get_chosen_due_date(record: dict, is_user_assignment: bool) -> dict | None:
    """Extract the chosen due date from assignment or user_assignment record."""
    if is_user_assignment:
        return record.get("due_dates")
    else:
        # For assignments, the chosen due date comes as a single object via foreign key
        due_dates_relation = record.get("due_dates")
        if isinstance(due_dates_relation, dict):
            return due_dates_relation
        elif isinstance(due_dates_relation, list) and due_dates_relation:
            return due_dates_relation[0]
        else:
            return None


def get_all_due_dates_for_assignment(
    record: dict, is_user_assignment: bool, assignment_id: str
) -> List[dict]:
    """Get all due dates for an assignment to count conflicts."""
    if is_user_assignment:
        assignment_data = record.get("assignments", {})
        return assignment_data.get("due_dates", []) if assignment_data else []
    else:
        # Fetch all due dates for this assignment separately
        result = (
            supabase.table("due_dates")
            .select("*")
            .eq("assignment_id", assignment_id)
            .execute()
        )
        return result.data if result.data else []


def count_conflicting_due_dates(all_due_dates: List[dict]) -> int:
    """Count the number of conflicting due dates (different dates)."""
    unique_dates = set()
    for dd in all_due_dates:
        if dd.get("date"):
            date_only = datetime.datetime.fromisoformat(
                dd["date"].replace("Z", "+00:00")
            ).date()
            unique_dates.add(date_only)
    return max(1, len(unique_dates))


def get_courses_with_colors(course_ids: List[str]) -> dict:
    """Get all courses and assign colors based on creation order."""
    if not course_ids:
        return {}

    result = supabase.table("courses").select("*").in_("id", course_ids).execute()

    if not result.data:
        return {}

    # Sort courses by created_at to ensure consistent color assignment
    sorted_courses = sorted(result.data, key=lambda x: x["created_at"])

    # Create a map of course_id to CourseInfo with color
    course_map = {}
    for index, course in enumerate(sorted_courses):
        color = colors[index % len(colors)]
        course_map[course["id"]] = CourseInfo(
            id=course["id"],
            created_at=course["created_at"],
            title=course.get("title"),
            color=color,
        )

    return course_map


def process_assignment(
    assignment: dict,
    user_assignment: dict | None,
    today: datetime.date,
    course_info: CourseInfo,
) -> AssignmentResponse | None:
    """Process a single assignment and return AssignmentResponse if valid."""
    # Skip if completed
    if user_assignment and user_assignment.get("completed_at"):
        return None

    # Determine which record to use
    record_to_use = user_assignment if user_assignment else assignment

    is_user_assignment = bool(user_assignment)

    # Get chosen due date
    chosen_due_date = get_chosen_due_date(record_to_use, is_user_assignment)

    # If no chosen due date exists, return with null values
    if not chosen_due_date or not chosen_due_date.get("date"):
        # Get all due dates to count conflicts
        all_due_dates = get_all_due_dates_for_assignment(
            record_to_use, is_user_assignment, assignment["id"]
        )
        conflicting_count = count_conflicting_due_dates(all_due_dates)

        return AssignmentResponse(
            assignment_id=assignment["id"],
            title=None,
            due_date=None,
            conflicting_due_date_count=conflicting_count,
            course=course_info,
        )

    # Parse and check due date
    due_date = datetime.datetime.fromisoformat(
        chosen_due_date["date"].replace("Z", "+00:00")
    )

    print(due_date)
    print(today)
    if due_date.date() < today:
        return None

    # Get all due dates and count conflicts
    all_due_dates = get_all_due_dates_for_assignment(
        record_to_use, is_user_assignment, assignment["id"]
    )
    conflicting_count = count_conflicting_due_dates(all_due_dates)

    return AssignmentResponse(
        assignment_id=assignment["id"],
        title=chosen_due_date.get("title", "Untitled Assignment"),
        due_date=due_date,
        conflicting_due_date_count=conflicting_count,
        course=course_info,
    )


@app.get("/assignments", response_model=List[AssignmentResponse])
async def get_user_assignments(current_user: Users = Depends(get_current_user)):
    """Get all upcoming assignments for user's courses."""
    try:
        today = datetime.datetime.now().date()

        # Step 1: Get user's course IDs
        course_ids = get_user_course_ids(str(current_user.id))
        if not course_ids:
            return []

        # Step 2: Get courses with color assignments
        courses_map = get_courses_with_colors(course_ids)

        # Step 3: Fetch assignments for courses
        assignments = fetch_assignments_for_courses(course_ids)
        if not assignments:
            return []

        # Step 4: Fetch user's assignment overrides
        user_assignments_map = fetch_user_assignments(str(current_user.id))

        # Step 5: Process each assignment
        response_assignments = []
        for assignment in assignments:
            course_id = assignment.get("course_id")
            course_info = courses_map.get(course_id)

            # Skip if we don't have course info
            if not course_info:
                continue

            user_assignment = user_assignments_map.get(assignment["id"])
            processed = process_assignment(
                assignment, user_assignment, today, course_info
            )
            if processed:
                response_assignments.append(processed)

        # Step 6: Sort by due date
        response_assignments.sort(key=lambda x: x.due_date)

        return response_assignments

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch assignments: {str(e)}",
        )


@app.post("/assignments/{assignment_id}/complete")
async def mark_assignment_complete(
    assignment_id: str, current_user: Users = Depends(get_current_user)
):
    """Mark an assignment as completed for the current user."""
    try:
        # First check if the assignment exists
        assignment_result = (
            supabase.table("assignments")
            .select("*")
            .eq("id", assignment_id)
            .single()
            .execute()
        )

        if not assignment_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found"
            )

        # Check if user already has a user_assignment record for this assignment
        existing_result = (
            supabase.table("user_assignments")
            .select("*")
            .eq("assignment_id", assignment_id)
            .eq("user_id", str(current_user.id))
            .execute()
        )

        if existing_result.data:
            # Update existing record with completed_at timestamp
            update_result = (
                supabase.table("user_assignments")
                .update({"completed_at": datetime.datetime.now().isoformat()})
                .eq("assignment_id", assignment_id)
                .eq("user_id", str(current_user.id))
                .execute()
            )

            return {
                "message": "Assignment marked as completed",
                "user_assignment": (
                    update_result.data[0] if update_result.data else None
                ),
            }
        else:
            # Create new user_assignment record
            insert_result = (
                supabase.table("user_assignments")
                .insert(
                    {
                        "assignment_id": assignment_id,
                        "user_id": str(current_user.id),
                        "completed_at": datetime.datetime.now().isoformat(),
                    }
                )
                .execute()
            )

            return {
                "message": "Assignment marked as completed",
                "user_assignment": (
                    insert_result.data[0] if insert_result.data else None
                ),
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark assignment as complete: {str(e)}",
        )


@app.get(
    "/assignments/{assignment_id}/dates", response_model=AssignmentDueDatesResponse
)
async def get_assignment_due_dates(
    assignment_id: str,
    page: int = 1,
    limit: int = 20,
    current_user: Users = Depends(get_current_user),
):
    """Get all due dates for a specific assignment with pagination."""
    try:
        # Validate page and limit
        if page < 1:
            page = 1
        if limit < 1 or limit > 100:
            limit = 20

        # Calculate offset
        offset = (page - 1) * limit

        # First check if the assignment exists and get its chosen_due_date_id
        assignment_result = (
            supabase.table("assignments")
            .select("*, courses!course_id(*, sources!course_id(*))")
            .eq("id", assignment_id)
            .single()
            .execute()
        )

        if not assignment_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found"
            )

        assignment = assignment_result.data
        chosen_due_date_id = assignment.get("chosen_due_date_id")

        # Check if user has a user_assignment override
        user_assignment_result = (
            supabase.table("user_assignments")
            .select("chosen_due_date_id")
            .eq("assignment_id", assignment_id)
            .eq("user_id", str(current_user.id))
            .execute()
        )

        if user_assignment_result.data:
            # User has an override, use their chosen_due_date_id
            chosen_due_date_id = user_assignment_result.data[0].get(
                "chosen_due_date_id"
            )

        # Get sources from the course
        sources = []
        if assignment.get("courses") and assignment["courses"].get("sources"):
            sources = assignment["courses"]["sources"]

        # Create a map of source URLs (we'll use the first source URL for simplicity)
        source_url = sources[0].get("url") if sources else None

        # Get total count of due dates for this assignment
        count_result = (
            supabase.table("due_dates")
            .select("*", count="exact", head=True)
            .eq("assignment_id", assignment_id)
            .execute()
        )
        total_count = count_result.count or 0

        # Fetch due dates with pagination
        due_dates_result = (
            supabase.table("due_dates")
            .select("*")
            .eq("assignment_id", assignment_id)
            .order("date", desc=False)
            .range(offset, offset + limit - 1)
            .execute()
        )

        # Process due dates
        due_dates_list = []
        for due_date in due_dates_result.data or []:
            due_date_obj = DueDate(
                source_url=source_url,
                title=due_date.get("title"),
                date=due_date.get("date"),
                selected=(due_date["id"] == chosen_due_date_id),
            )
            due_dates_list.append(due_date_obj)

        # Determine if there are more pages
        has_more = offset + limit < total_count

        return AssignmentDueDatesResponse(
            assignment_id=UUID4(assignment_id),
            data=due_dates_list,
            hasMore=has_more,
            total=total_count,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch assignment due dates: {str(e)}",
        )


@app.post("/sync-course")
async def sync_courses(
    request: CourseSyncRequest, current_user: Users = Depends(get_current_user)
):
    """
    Create a job sync group and job syncs for the specified courses.
    For each course, finds all sources and creates job syncs.
    """
    try:
        # Create a new job_sync_group
        job_sync_group_data = {"user_id": str(current_user.id)}

        job_sync_group_result = (
            supabase.table("job_sync_groups").insert(job_sync_group_data).execute()
        )

        if not job_sync_group_result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create job sync group",
            )

        job_sync_group_id = job_sync_group_result.data[0]["id"]
        created_job_syncs = []

        # For each course, find all sources and create job syncs
        for course_id in request.course_ids:
            # Get all sources for this course
            sources_result = (
                supabase.table("sources")
                .select("*")
                .eq("course_id", str(course_id))
                .execute()
            )

            if sources_result.data:
                # Create a job_sync for each source
                for source in sources_result.data:
                    job_sync_data = {
                        "job_sync_group_id": job_sync_group_id,
                        "course_id": str(course_id),
                        "source_id": source["id"],
                    }

                    job_sync_result = (
                        supabase.table("job_syncs").insert(job_sync_data).execute()
                    )

                    if job_sync_result.data:
                        created_job_syncs.append(job_sync_result.data[0])

        return {
            "job_sync_group_id": job_sync_group_id,
            "job_syncs_created": len(created_job_syncs),
            "job_syncs": created_job_syncs,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create sync jobs: {str(e)}",
        )


@app.post("/sync-course/{sync_job_id}/scrape")
async def scrape_course_endpoint(
    sync_job_id: str, current_user: Users = Depends(get_current_user)
):
    """
    Scrape a course website based on the sync job ID.
    Gets the source URL from the job_sync and updates the scraped_tree column.
    """
    try:
        # Get the job_sync record to find the source
        job_sync_result = (
            supabase.table("job_syncs")
            .select("*, sources!source_id(*)")
            .eq("id", sync_job_id)
            .single()
            .execute()
        )

        if not job_sync_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Job sync not found"
            )

        job_sync = job_sync_result.data
        source = job_sync.get("sources")

        if not source or not source.get("url"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No source URL found for this job sync",
            )

        source_url = source["url"]

        # Check if user has auth details for this source
        # auth_details_result = (
        #     supabase.table("user_auth_details")
        #     .select("cookies")
        #     .eq("source_id", job_sync["source_id"])
        #     .single()
        #     .execute()
        # )

        # cookies = None
        # if auth_details_result.data and auth_details_result.data.get("cookies"):
        #     cookies = auth_details_result.data["cookies"]

        cookies = [
            {
                "domain": "www.gradescope.com",
                "hostOnly": True,
                "httpOnly": True,
                "name": "signed_token",
                "path": "/",
                "sameSite": "no_restriction",
                "secure": True,
                "session": True,
                "storeId": "0",
                "value": "a1VUdGJnVzd2L0N4VmxxSHpPSFFzT2R5ZWFreHZHTFhTdnhOckYwRUp6az0tLXl2UXU4QmJBL0lxKzg5U3NNWTZwSEE9PQ%3D%3D--828dca5aabe771bda89b265a2f8d79106a0f3543",
            },
            {
                "domain": "www.gradescope.com",
                "expirationDate": 1791854981.807883,
                "hostOnly": True,
                "httpOnly": False,
                "name": "remember_me",
                "path": "/",
                "sameSite": "no_restriction",
                "secure": True,
                "session": False,
                "storeId": "0",
                "value": "WUg4cUtWOWZZRnR1NUovamdLalJqUT09LS1UYlhHK25OVk05R2JENXpwVWxNbml3PT0%3D--07c609883c0600e60bc9abc1857c234ce1c490ee",
            },
            {
                "domain": "www.gradescope.com",
                "hostOnly": True,
                "httpOnly": True,
                "name": "_gradescope_session",
                "path": "/",
                "sameSite": "no_restriction",
                "secure": True,
                "session": True,
                "storeId": "0",
                "value": "amF5MU05VDFobGJSYU43Q1VXWTNBcFlDRjFUYnRTME91dWRFV3VCQUxKSWVtUUVSWGZweGhydCszTklHOTNKbVhHbnliM2dqSFRoaUpReGl4MTQ4bEtac0hhS0xKQTJ5cGpwNDdVUWtPenFpdEFqbTdDTkNSbUFjamh2RzZZTTFNaGhmSWlTMU04ZmoyaGhJK3dhVEpQV0ZHQ1FFOHcyQkw2ZDgzc3pHWExUUnhGU0RhU21SclFuTEl4ckFQbGFMYmNSRVNiVjZpc2FwYlRvRzhSaGo3TWtOakZ4Q0NzL0tOUVg4VkhaWm83Y1VsQVB0QU10ZjBSd2hqNW1DWDBGTkVMSkdtU2RJRGVzdkVWWDVMUm5mUjMzU21XUGdScUoyZXVmOVBKdStabW5rM0d3SFFtdnVxMTAraXNCS1R0dG5nc2tHWGVFY0dmTmZVY1dLUk5hdElzTDRweHd4N3NHQnBiN1JZNnl0NmgvalluWVJjZmtuaThTZk5wVVFmcUNvYTVkUEN1WmRsNUQveHU2V0cyVHhOblBGTzkwV3BJTk1BK2MyQkdLQjV6Y2R6WGhyNU1CVzMwMXJPZElaWnA2RS0tSXZseDVwMzdMaExwUkJzNUpxQUpCUT09--5067c60488ea3a6f00432bf45352559263c0e5a8",
            },
        ]

        # Create scraper instance with supabase client
        scraper = Scraper(supabase_client=supabase, job_sync_id=sync_job_id)

        # Run the scraping
        scraped_tree = await scraper.scrape_course(source_url, cookies)

        # Update the job_sync with the scraped tree
        update_result = (
            supabase.table("job_syncs")
            .update({"scraped_tree": scraped_tree})
            .eq("id", sync_job_id)
            .execute()
        )

        if not update_result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update job sync with scraped data",
            )

        return {
            "message": "Course scraped successfully",
            "sync_job_id": sync_job_id,
            "nodes_scraped": len(scraped_tree.get("children", [])) + 1,
            "assignment_pages_found": sum(
                1
                for node in _flatten_tree(scraped_tree)
                if node.get("assignment_data_found")
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to scrape course: {str(e)}",
        )


def _flatten_tree(node):
    """Helper function to flatten tree structure for counting"""
    nodes = [node]
    for child in node.get("children", []):
        nodes.extend(_flatten_tree(child))
    return nodes


@app.post("/sync-course/{sync_job_id}/assignments")
async def find_assignments_endpoint(
    sync_job_id: str, current_user: Users = Depends(get_current_user)
):
    """
    Find unique assignments from the scraped course data.
    Reads scraped_tree from job_sync and creates assignment records.
    """
    try:
        # Get the job_sync record to get scraped_tree and course_id
        job_sync_result = (
            supabase.table("job_syncs")
            .select("*, courses!course_id(*)")
            .eq("id", sync_job_id)
            .single()
            .execute()
        )

        if not job_sync_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Job sync not found"
            )

        job_sync = job_sync_result.data
        scraped_tree = job_sync.get("scraped_tree")
        course_id = job_sync.get("course_id")

        if not scraped_tree:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No scraped tree found. Please run scraping first.",
            )

        if not course_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No course_id found for this job sync",
            )

        # Find unique assignments using the imported function
        assignments = await find_unique_assignments(scraped_tree, supabase)

        # Insert assignments into database
        created_assignments = []
        for assignment in assignments:
            assignment_data = {
                "title": assignment.title,
                "description": assignment.description,
                "course_id": course_id,
                "chosen_due_date_id": None,  # NULL as requested
            }

            try:
                result = supabase.table("assignments").insert(assignment_data).execute()
                if result.data:
                    created_assignments.extend(result.data)
            except Exception as e:
                print(f"Error inserting assignment: {e}")
                # Continue with other assignments even if one fails

        return {
            "message": "Assignments found and created successfully",
            "sync_job_id": sync_job_id,
            "assignments_found": len(assignments),
            "assignments_created": len(created_assignments),
            "assignments": created_assignments,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to find assignments: {str(e)}",
        )


@app.post("/sync-course/{sync_job_id}/due-dates")
async def find_due_dates_endpoint(
    sync_job_id: str, current_user: Users = Depends(get_current_user)
):
    """
    Find due dates for assignments from the scraped course data.
    Reads scraped_tree and assignments from database, then creates due_date records.
    """
    try:
        # Get the job_sync record to get scraped_tree
        job_sync_result = (
            supabase.table("job_syncs")
            .select("scraped_tree")
            .eq("id", sync_job_id)
            .single()
            .execute()
        )

        if not job_sync_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Job sync not found"
            )

        scraped_tree = job_sync_result.data.get("scraped_tree")

        if not scraped_tree:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No scraped tree found. Please run scraping first.",
            )

        # Get assignments for this job_sync_id
        assignments = await get_assignments_from_db(supabase, sync_job_id)

        if not assignments:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No assignments found for this job sync. Please run assignment extraction first.",
            )

        # Find due dates
        due_dates = await find_due_dates(scraped_tree, assignments, supabase)

        # Insert due dates into database
        created_due_dates = []
        for due_date in due_dates:
            due_date_data = {
                "title": due_date.title,
                "date": due_date.date.isoformat(),
                "description": due_date.description,
                "assignment_id": due_date.assignment_id,
                "url": due_date.url,
                "date_certain": True,  # You may want to adjust this based on your logic
                "time_certain": False,  # You may want to adjust this based on your logic
            }

            try:
                result = supabase.table("due_dates").insert(due_date_data).execute()
                if result.data:
                    created_due_dates.extend(result.data)
            except Exception as e:
                print(f"Error inserting due date: {e}")
                # Continue with other due dates even if one fails

        # Group due dates by assignment and select the best one for each
        assignments_updated = 0
        due_dates_by_assignment = {}
        for due_date in created_due_dates:
            assignment_id = due_date["assignment_id"]
            if assignment_id not in due_dates_by_assignment:
                due_dates_by_assignment[assignment_id] = []
            due_dates_by_assignment[assignment_id].append(due_date)

        # For each assignment, select the best due date and update the assignment
        for assignment in assignments:
            assignment_id = assignment["id"]
            assignment_due_dates = due_dates_by_assignment.get(assignment_id, [])

            if assignment_due_dates:
                try:
                    # Select the best due date using AI
                    best_due_date_id = await select_best_due_date(
                        assignment_due_dates, assignment
                    )

                    if best_due_date_id:
                        # Update the assignment's chosen_due_date_id
                        update_result = (
                            supabase.table("assignments")
                            .update({"chosen_due_date_id": best_due_date_id})
                            .eq("id", assignment_id)
                            .execute()
                        )

                        if update_result.data:
                            assignments_updated += 1
                            print(
                                f"Updated assignment {assignment_id} with chosen due date {best_due_date_id}"
                            )

                except Exception as e:
                    print(
                        f"Error selecting/updating best due date for assignment {assignment_id}: {e}"
                    )

        return {
            "message": "Due dates found and created successfully",
            "sync_job_id": sync_job_id,
            "due_dates_found": len(due_dates),
            "due_dates_created": len(created_due_dates),
            "assignments_updated": assignments_updated,
            "due_dates": created_due_dates,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to find due dates: {str(e)}",
        )


def main():
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
