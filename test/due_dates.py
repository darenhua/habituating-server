import json
import os
from typing import List, Dict, Any
from unique import Assignment, process_assignment_nodes
from pydantic import BaseModel, Field
from openai import AsyncOpenAI
from markdownify import markdownify as md
import datetime
from supabase import Client
from test import Node


client = AsyncOpenAI()

OPENAI_CONTEXT_LIMIT = 80000


class DueDateSchema(BaseModel):
    title: str
    date: datetime.datetime
    description: str = Field(
        description="Description of what this page describes about the assignment"
    )


class DueDateResponse(DueDateSchema):
    assignment_id: str
    url: str


class DueDates(BaseModel):
    due_dates: List[DueDateSchema] = Field(default_factory=list)


async def get_assignments_from_db(
    supabase: Client, job_sync_id: str
) -> List[Dict[str, Any]]:
    """Get assignments from database for a specific job_sync_id"""
    # First get the course_id from job_sync
    job_sync_result = (
        supabase.table("job_syncs")
        .select("course_id")
        .eq("id", job_sync_id)
        .single()
        .execute()
    )

    if not job_sync_result.data:
        return []

    course_id = job_sync_result.data["course_id"]

    # Get all assignments for this course
    assignments_result = (
        supabase.table("assignments")
        .select("*")
        .eq("course_id", course_id)
        .eq("job_sync_id", job_sync_id)
        .execute()
    )

    return assignments_result.data if assignments_result.data else []


async def process_markdown_for_due_dates(
    markdown_contents: List[Dict[str, str]],
    assignment: Dict[str, Any],
    due_dates: List[DueDateResponse],
):
    """Process markdown content to find due dates for a specific assignment"""
    for content in markdown_contents:
        system_prompt = f"""Your job is to find out as much due date information as you can about when my homework assignment might be due. You will be provided with markdown pages of my college course website. Here are details about my homework assignment:

<assignment_title>
{assignment['title']}
</assignment_title>
<assignment_description>
{assignment['description']}
</assignment_description>

If there are no details about the assignment on a given page, then do not output any due dates."""

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Content from {content['url']}:\n\n{content['markdown']}",
            },
        ]

        try:
            response = await client.responses.parse(
                model="gpt-5-mini",
                input=messages,
                text_format=DueDates,
            )

            if response.output_parsed and response.output_parsed.due_dates:
                for due_date_schema in response.output_parsed.due_dates:
                    due_date = DueDateResponse(
                        title=due_date_schema.title,
                        date=due_date_schema.date,
                        description=due_date_schema.description,
                        assignment_id=assignment["id"],  # Use actual assignment ID
                        url=content['url'],
                    )
                    due_dates.append(due_date)
        except Exception as e:
            print(f"Error processing {content['url']}: {e}")




async def find_due_dates(
    scraped_tree: Dict[str, Any], assignments: List[Dict[str, Any]], supabase: Client
) -> List[DueDateResponse]:
    """Find due dates for assignments from scraped tree"""
    due_dates = []

    # Reconstruct Node tree
    root = Node.from_dict(scraped_tree)
    
    # Get all markdown content from assignment pages using the imported function
    markdown_contents = []
    await process_assignment_nodes(root, markdown_contents, supabase)
    
    # Process each assignment against all markdown contents
    for assignment in assignments:
        print(f"\nProcessing assignment: {assignment['title']}")
        print(f"Description: {assignment['description']}")
        print("-" * 50)
        
        await process_markdown_for_due_dates(markdown_contents, assignment, due_dates)

    return due_dates


async def main():
    # For testing purposes only
    import json
    from pathlib import Path

    with open("scraped_tree.json", "r") as f:
        tree_data = json.load(f)

    # Mock assignments for testing
    assignments = [
        {"id": "test-id", "title": "Test Assignment", "description": "Test Description"}
    ]

    due_dates = await find_due_dates(tree_data, assignments, None)

    # Export to JSON file
    output_path = "due_dates.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json_content = {
            "due_dates": [due_date.model_dump(mode="json") for due_date in due_dates]
        }
        f.write(json.dumps(json_content, indent=2))

    print(f"\nDue dates have been exported to {output_path}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
