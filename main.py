from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import uvicorn
from supabase import create_client, Client
import os
from typing import Optional
from entities.fastapi.schema_public_latest import Users, Courses, Sources
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import List
from pydantic import UUID4
import datetime

load_dotenv()

app = FastAPI()

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


class CourseWithColor(BaseModel):
    """Course model with color attribute."""
    id: UUID4
    created_at: datetime.datetime
    title: str | None = None
    sources: List[Sources] | None = None
    color: str


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
        # Query to get all courses for the user with their sources
        # Join user_courses -> courses -> sources
        result = (
            supabase.table("user_courses")
            .select("*, courses(*, sources(*))")
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

            # Create CourseWithColor instance
            course_with_color = CourseWithColor(**course_data, color=color)
            courses_with_colors.append(course_with_color)

        return courses_with_colors

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch courses: {str(e)}",
        )


def main():
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
