"""
Due date extraction with one-to-one assignment mapping
Processes all content together for accurate date determination
"""
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from markdownify import markdownify
from supabase import Client
from dotenv import load_dotenv

load_dotenv()

class AssignmentDueDate(BaseModel):
    """Single due date for an assignment"""
    assignment_id: str
    assignment_title: str
    date: str = Field(description="The due date in ISO format or human-readable format")
    date_certain: bool = Field(
        description="True if date is explicitly stated, False if inferred"
    )
    time_certain: bool = Field(
        description="True if specific time is given, False if just date"
    )
    confidence: float = Field(
        description="Confidence score 0-1 for this due date"
    )
    source_urls: List[str] = Field(
        description="URLs where this due date was found"
    )
    reasoning: str = Field(
        description="Explanation of how this due date was determined"
    )

class SingleAssignmentDueDate(BaseModel):
    """Single due date result for one assignment"""
    due_date: Optional[AssignmentDueDate]

class DueDateFinder:
    def __init__(self, supabase_client: Client = None):
        self.supabase = supabase_client
        self.client = AsyncOpenAI()
        self.storage_bucket = "scraped-html"
    
    async def find_due_dates(
        self,
        scraped_tree: Dict[str, Any],
        assignments: List[Dict],
        job_sync_id: str
    ) -> List[AssignmentDueDate]:
        """
        Extract ONE due date per assignment using their source_page_paths.
        This provides better accuracy by only loading relevant pages.
        """
        print(f"\n=== Due Date Extraction (Revised) ===")
        print(f"Finding due dates for {len(assignments)} assignments")
        
        all_due_dates = []
        
        # Process each assignment individually using its source_page_paths
        for assignment in assignments:
            print(f"  Extracting due date for: {assignment['title']}")
            
            # Get content from assignment's source pages
            assignment_content = await self.collect_assignment_content(assignment)
            print(f"    Collected content from {len(assignment_content)} pages")
            
            # Extract due date for this specific assignment
            due_date = await self.extract_single_due_date(
                assignment,
                assignment_content
            )
            
            if due_date:
                all_due_dates.append(due_date)
        
        print(f"✓ Found due dates for {len(all_due_dates)} assignments")
        
        # Step 3: Validate and store
        validated_dates = self.validate_due_dates(all_due_dates, assignments)
        
        return validated_dates
    
    async def collect_assignment_content(self, assignment: Dict) -> List[Dict]:
        """
        Collect content from an assignment's source_page_paths.
        Returns list of {html_path, content} dictionaries.
        """
        assignment_content = []
        source_paths = assignment.get("source_page_paths", [])
        
        if not source_paths:
            print(f"    No source pages found for assignment: {assignment['title']}")
            return assignment_content
        
        for html_path in source_paths:
            try:
                # Load HTML content from storage
                html_content = await self.load_html_from_storage(html_path)
                markdown = markdownify(html_content, heading_style="closed")
                
                assignment_content.append({
                    "html_path": html_path,
                    "content": markdown
                })
                
            except Exception as e:
                print(f"    Error loading content from {html_path}: {e}")
        
        return assignment_content
    
    # Removed extract_all_due_dates method - now handled in find_due_dates
    
    async def extract_single_due_date(
        self,
        assignment: Dict,
        assignment_content: List[Dict]
    ) -> Optional[AssignmentDueDate]:
        """
        Extract due date for a single assignment using its source page content.
        Returns exactly one due date (or None if not found).
        """
        
        # Format content from assignment's source pages
        formatted_content = ""
        source_urls = []
        
        for idx, page_content in enumerate(assignment_content, 1):
            formatted_content += f"\n\n{'='*60}\n"
            formatted_content += f"SOURCE PAGE {idx}: {page_content['html_path']}\n"
            formatted_content += f"{'='*60}\n"
            formatted_content += page_content['content'][:5000]  # Limit per-page content
            source_urls.append(page_content['html_path'])
        
        if not formatted_content.strip():
            print(f"    No content available for assignment: {assignment['title']}")
            return None
        
        prompt = f"""You are analyzing course content to find the due date for ONE specific assignment.

ASSIGNMENT TO FIND DUE DATE FOR:
ID: {assignment['id']}
Title: {assignment['title']}
Description: {assignment['description']}

INSTRUCTIONS:
1. Find the most accurate due date for THIS SPECIFIC assignment
2. Look for explicit mentions of deadlines, due dates, or submission times
3. Consider calendar pages, syllabus sections, and assignment descriptions
4. If multiple dates are mentioned for this assignment, use the most authoritative one
5. Provide:
   - The due date (if found, otherwise null)
   - Whether the date is certain or inferred
   - Whether a specific time is mentioned
   - Confidence level (0-1)
   - Which source pages mentioned this date (use the html_path values)
   - Reasoning for your conclusion

If you cannot find a due date for this assignment, return null for the date and explain why.

CONTENT FROM ASSIGNMENT'S SOURCE PAGES:
{formatted_content[:30000]}  # Total content limit

Return exactly ONE due date result for this assignment."""

        # Single LLM call for this assignment
        try:
            response = await self.client.responses.parse(
                model="gpt-4o-mini",
                input=[
                    {
                        "role": "system",
                        "content": "You are an expert at extracting assignment due dates from course materials."
                    },
                    {"role": "user", "content": prompt}
                ],
                text_format=SingleAssignmentDueDate
            )
            
            result = response.output_parsed
            return result.due_date
        except Exception as e:
            print(f"    Error extracting due date: {e}")
            return None
    
    async def load_html_from_storage(self, html_path: str) -> str:
        """Load HTML from Supabase storage"""
        if self.supabase and not html_path.startswith("/"):
            try:
                response = self.supabase.storage.from_(self.storage_bucket).download(html_path)
                return response.decode("utf-8")
            except Exception as e:
                print(f"Error downloading from storage: {e}")
                raise
        else:
            # Local file fallback
            from pathlib import Path
            return Path(html_path).read_text()
    
    def validate_due_dates(
        self,
        due_dates: List[AssignmentDueDate],
        assignments: List[Dict]
    ) -> List[AssignmentDueDate]:
        """
        Validate and clean the extracted due dates.
        Ensures one-to-one mapping with assignments.
        """
        # Create assignment lookup
        assignment_map = {a['id']: a for a in assignments}
        
        validated = []
        for due_date in due_dates:
            # Verify assignment exists
            if due_date.assignment_id not in assignment_map:
                print(f"Warning: Due date for unknown assignment {due_date.assignment_id}")
                continue
            
            # Validate date format if present
            if due_date.date:
                try:
                    # Try to parse the date (add date parsing logic)
                    validated.append(due_date)
                    print(f"✓ {due_date.assignment_title}: {due_date.date} (confidence: {due_date.confidence:.2f})")
                except Exception as e:
                    print(f"Invalid date format for {due_date.assignment_title}: {due_date.date}")
            else:
                print(f"⚠ No due date found for: {due_date.assignment_title}")
                # Still include it with null date
                validated.append(due_date)
        
        # Check for missing assignments
        found_ids = {dd.assignment_id for dd in validated}
        for assignment in assignments:
            if assignment['id'] not in found_ids:
                print(f"⚠ No due date entry for assignment: {assignment['title']}")
                # Create placeholder entry
                validated.append(AssignmentDueDate(
                    assignment_id=assignment['id'],
                    assignment_title=assignment['title'],
                    date=None,
                    date_certain=False,
                    time_certain=False,
                    confidence=0.0,
                    source_urls=[],
                    reasoning="No due date found in any course materials"
                ))
        
        return validated

    async def update_assignments_with_due_dates(
        self,
        due_dates: List[AssignmentDueDate],
        job_sync_id: str
    ):
        """
        Update assignments table with their due dates.
        Implements one-to-one relationship.
        """
        for due_date in due_dates:
            if due_date.date:
                # Create single due_date record
                due_date_record = {
                    "assignment_id": due_date.assignment_id,
                    "date": due_date.date,
                    "date_certain": due_date.date_certain,
                    "time_certain": due_date.time_certain,
                    "title": f"Due: {due_date.assignment_title}",
                    "description": due_date.reasoning,
                    "url": due_date.source_urls[0] if due_date.source_urls else None
                }
                
                result = self.supabase.table("due_dates").insert(due_date_record).execute()
                
                if result.data:
                    # Update assignment with chosen_due_date_id
                    due_date_id = result.data[0]["id"]
                    self.supabase.table("assignments")\
                        .update({"chosen_due_date_id": due_date_id})\
                        .eq("id", due_date.assignment_id)\
                        .execute()