from openai import AsyncOpenAI
import json
from pathlib import Path
from markdownify import markdownify
from typing import Dict, Any, List, Optional
from test import Node
from pydantic import BaseModel, Field
from supabase import Client

client = AsyncOpenAI()


async def process_assignment_nodes(
    node: Node,
    markdown_content: List[Dict[str, str]],
    supabase: Client = None,
    storage_bucket: str = "scraped-html",
):
    """Recursively process nodes and collect markdown content from assignment pages"""
    if node.assignment_data_found and node.html_path:
        # Read HTML from Supabase storage or local file
        if (
            supabase and node.html_path.startswith("/") == False
        ):  # Storage path format: job_sync_id/hash.html
            try:
                # Download from Supabase storage
                response = supabase.storage.from_(storage_bucket).download(
                    node.html_path
                )
                html_content = response.decode("utf-8")
            except Exception as e:
                print(f"Error downloading from storage: {e}")
                return

        # Convert to markdown
        markdown = markdownify(html_content, heading_style="closed")

        markdown_content.append(
            {
                "url": node.url,
                "title": node.title,
                "html_path": node.html_path,
                "markdown": markdown,
            }
        )

        print(f"Processed: {node.title} ({node.url})")

    # Process children
    for child in node.children:
        await process_assignment_nodes(
            child, markdown_content, supabase, storage_bucket
        )


class Assignment(BaseModel):
    title: str
    description: str = Field(description="Describe the assignment")
    repeated: bool = Field(
        description="True if the assignment was already in existing assignments list"
    )
    # url: str = Field(exclude=True)


class UniqueAssignmentsFound(BaseModel):
    unique_assignments: List[Assignment]

    def pretty_format(self):
        """Return all unique assignments in a pretty formatted string"""
        output = ["\n=== Existing Assignments Found ==="]
        if not self.unique_assignments:
            output.append("<empty array>")
            return "\n".join(output)

        for i, assignment in enumerate(self.unique_assignments, 1):
            output.append(f"\nTitle: {assignment.title}")
            output.append("-" * (len(assignment.title) + 3))
            output.append("Description: " + assignment.description)
            output.append("")

        return "\n".join(output)

    # existing_assignments: List[Assignment]


async def find_unique_assignments(
    scraped_tree: Dict[str, Any], supabase: Client = None
) -> List[Assignment]:
    """Find unique assignments from a scraped tree structure"""
    # Reconstruct Node tree
    root = Node.from_dict(scraped_tree)
    print("ROOT", root.to_dict())

    # Process all nodes with assignment data
    markdown_content = []
    await process_assignment_nodes(root, markdown_content, supabase)

    assignments_found = UniqueAssignmentsFound(
        unique_assignments=[],
    )

    print("HELLO", markdown_content)

    for content in markdown_content:

        prompt = f"""Your job is to look through this course website page, and find any homework assignments that that a college student would want to know the deadlines of. 

You must carefully discern whether a new assignment that you find on this page is not one that I've already found. The assignments that I've already found are: 
        
{assignments_found.pretty_format()}. 
        
You must read the description and titles of the existing assignments, and then use that to figure out if an new assignment that you find is repeated or unique. Note that a homework title might be described slightly differently on this page compared to the existing assignment, so use your best judgement to determine if they are different assignments. To reason about this, imagine you are a student -- would you care about the deadline of both assignments, or would only one matter because they're the same assignment?

A student would not want to miss a deadline because you did not find an assignment on the page. Do not include due date details in the description.

Here is the course website markdown:

{content["markdown"]}
"""

        response = await client.responses.parse(
            model="gpt-5-mini",
            input=[
                {
                    "role": "system",
                    "content": "You are analyzing course website content to find unique homework assignments.",
                },
                {"role": "user", "content": prompt},
            ],
            text_format=UniqueAssignmentsFound,
        )

        result: UniqueAssignmentsFound = response.output_parsed
        for assignment in result.unique_assignments:
            if not assignment.repeated:
                assignments_found.unique_assignments.append(assignment)
            else:
                print("REPEATED", assignment.title)

    print(assignments_found.pretty_format())
    return assignments_found.unique_assignments


async def main():
    # Load tree from JSON for testing
    with open("scraped_tree.json", "r") as f:
        tree_data = json.load(f)

    assignments = await find_unique_assignments(tree_data)

    # Export assignments to JSON file
    output_path = Path("unique_assignments.json")
    assignments_data = {"unique_assignments": [a.model_dump() for a in assignments]}
    output_path.write_text(json.dumps(assignments_data, indent=2), encoding="utf-8")

    print(f"\nAssignments have been exported to {output_path}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
