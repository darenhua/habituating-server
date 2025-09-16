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
    return max(0, len(unique_dates) - 1)


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
    if due_date.date() <= today:
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
                .insert({
                    "assignment_id": assignment_id,
                    "user_id": str(current_user.id),
                    "completed_at": datetime.datetime.now().isoformat(),
                })
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


def main():
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
