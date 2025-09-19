import json
import os
from typing import List
from unique import Assignment
from pydantic import BaseModel, Field
from openai import OpenAI
from markdownify import markdownify as md
import datetime


client = OpenAI()

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


def get_assignments() -> List[Assignment]:
    with open("unique_assignments.json", "r") as f:
        data = json.load(f)

    assignments = []
    for item in data["unique_assignments"]:
        assignment = Assignment(
            title=item["title"],
            description=item["description"],
            repeated=item["repeated"],
        )
        assignments.append(assignment)

    return assignments


def convert_html_to_markdown(html_file_path: str) -> str:
    with open(html_file_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    return md(html_content)


def main():
    assignments = get_assignments()
    due_dates = []

    for assignment in assignments[:1]:
        print(f"\nProcessing assignment: {assignment.title}")
        print(f"Description: {assignment.description}")
        print(f"Repeated: {assignment.repeated}")
        print("-" * 50)

        system_prompt = f"""Your job is to find out as much due date information as you can about when my homework assignment might be due. You will be provided with markdown pages of my college course website. Here are details about my homework assignment:

<assignment_title>
{assignment.title}
</assignment_title>
<assignment_description>
{assignment.description}
</assignment_description>

If there are no details about the assignment on a given page, then do not output any due dates."""

        html_files = [f for f in os.listdir("storage") if f.endswith(".html")]

        for html_file in html_files:
            html_path = os.path.join("storage", html_file)
            markdown_content = convert_html_to_markdown(html_path)

            # Create a fresh message list for each file
            messages = [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"Content from {html_file}:\n\n{markdown_content}",
                },
            ]

            # Make individual request for each file
            try:
                response = client.responses.parse(
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
                            assignment_id=assignment.title,
                            url=html_file,
                        )
                        due_dates.append(due_date)
            except Exception as e:
                print(f"Error processing {html_file}: {e}")
    # Create a list of DueDateResponse objects for JSON export
    export_due_dates = [
        DueDateResponse(
            title=due_date.title,
            date=due_date.date,
            description=due_date.description,
            assignment_id=due_date.assignment_id,
            url=due_date.url,
        )
        for due_date in due_dates
    ]

    # Export to JSON file
    output_path = "due_dates.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json_content = {
            "due_dates": [
                due_date.model_dump(mode="json") for due_date in export_due_dates
            ]
        }
        f.write(json.dumps(json_content, indent=2))

    # Display all collected due dates
    print("\n" + "=" * 50)
    print("ALL DUE DATES FOUND:")
    print("=" * 50)
    for due_date in due_dates:
        print(f"\nAssignment: {due_date.assignment_id}")
        print(f"Title: {due_date.title}")
        print(f"Due Date: {due_date.date}")
        print(f"Description: {due_date.description}")
        print(f"Source: {due_date.url}")
        print("-" * 30)

    print(f"\nDue dates have been exported to {output_path}")


if __name__ == "__main__":
    main()
