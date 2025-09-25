"""
Assignment extraction with page-level tracking and deduplication
Based on test/unique.py but with page-level processing
"""
import asyncio
from typing import List, Dict, Any, Optional
from pathlib import Path
import json
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from markdownify import markdownify
from supabase import Client
from dotenv import load_dotenv
load_dotenv()
# Copy Assignment model from test/unique.py
class Assignment(BaseModel):
    title: str = Field(description="Title of the assignment")
    description: str = Field(description="Describe the assignment")
    repeated: bool = Field(description="True if this assignment was found in previous assignments, False if it's new")
    
    # Add new fields for page tracking
    content_hash: Optional[str] = None
    source_url: Optional[str] = None
class PageAssignments(BaseModel):
    """Assignments found on a specific page"""
    assignments: List[Assignment]
    page_url: str
    content_hash: str
class AssignmentExtractor:
    def __init__(self, supabase_client: Client = None):
        self.supabase = supabase_client
        self.client = AsyncOpenAI()
        self.storage_bucket = "scraped-html"
    
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
            return Path(html_path).read_text()
    
    async def extract_assignments_from_page(
        self,
        node_data: Dict,
        previous_assignments: List[Dict] = None
    ) -> List[Assignment]:
        """
        Extract assignments from a single page with context of previous assignments
        """
        if previous_assignments is None:
            previous_assignments = []
        
        # Load HTML content
        html_content = await self.load_html_from_storage(node_data["html_path"])
        markdown = markdownify(html_content, heading_style="closed")
        
        # Format previous assignments for context
        previous_context = ""
        if previous_assignments:
            previous_context = f"""
Previously found assignments in this ENTIRE COURSE:
{self.format_assignments(previous_assignments)}
Note: These are ALL assignments that were previously found anywhere in this course.
"""
        
        # Prompt for extraction
        prompt = f"""Your job is to find homework assignments on this course webpage.
A student needs to know about deadlines for these assignments.
{previous_context}

For each assignment you find on this page, you must determine:
- If it matches any assignment in the "Previously found assignments" list above, mark it as repeated: true
- If it's a completely new assignment not in that list, mark it as repeated: false

IMPORTANT: 
- An assignment is "repeated" if it appears to be the same assignment as one in the previous list
- Use your judgment to match assignments even if wording differs slightly
- Do not include due date details in the description
- Focus on the core assignment content, not formatting differences

Find ALL assignments mentioned on this page.

Page content:
{markdown[:8000]}  # Limit context size
"""
        
        # Extract using LLM
        response = await self.client.responses.parse(
            model="gpt-4o-mini",
            input=[
                {
                    "role": "system",
                    "content": "You are analyzing a course webpage to extract homework assignments."
                },
                {"role": "user", "content": prompt}
            ],
            text_format=PageAssignments
        )
        
        result = response.output_parsed
        
        # Add page metadata to each assignment
        assignments = []
        for assignment in result.assignments:
            assignment.content_hash = node_data["content_hash"]
            assignment.source_url = node_data["url"]
            assignments.append(assignment)
        
        return assignments
    
    def format_assignments(self, assignments: List[Dict]) -> str:
        """Format assignments for display in prompt"""
        if not assignments:
            return "None"
        
        formatted = []
        for idx, assignment in enumerate(assignments, 1):
            formatted.append(f"{idx}. {assignment['title']}: {assignment['description']}")
        
        return "\n".join(formatted)
    
    async def extract_all_assignments(
        self,
        scraped_tree: Dict[str, Any],
        job_sync_id: str
    ) -> List[Assignment]:
        """
        Main entry point: Extract assignments from all pages in tree
        """
        all_assignments = []
        
        # Collect all nodes (no longer filtering by assignment_data_found)
        nodes_to_process = []
        
        def collect_nodes(node: Dict):
            # Process all nodes that have content_changed=True or are new
            if node.get("content_changed", True):
                nodes_to_process.append(node)
            for child in node.get("children", []):
                collect_nodes(child)
        
        collect_nodes(scraped_tree)
        
        print(f"\n=== Assignment Extraction ===")
        print(f"Found {len(nodes_to_process)} changed/new pages to process")
        
        # Get course_id from job_sync to find previous assignments
        course_id = None
        if self.supabase:
            job_result = self.supabase.table("job_syncs").select("course_id").eq("id", job_sync_id).execute()
            if job_result.data:
                course_id = job_result.data[0]["course_id"]
        
        # Get ALL previous assignments for this course
        all_previous_assignments = []
        if self.supabase and course_id:
            prev_result = self.supabase.table("assignments").select("title, description").eq("course_id", course_id).execute()
            all_previous_assignments = prev_result.data if prev_result.data else []
            print(f"Found {len(all_previous_assignments)} previous assignments for context")
        
        # Process each changed/new page
        for node in nodes_to_process:
            try:
                print(f"↻ Processing page: {node['url']}")
                
                # Extract assignments using ALL course assignments for context
                assignments = await self.extract_assignments_from_page(
                    node,
                    all_previous_assignments
                )
                
                print(f"  Found {len(assignments)} assignments")
                
                # Handle database updates for each assignment
                for assignment in assignments:
                    await self.handle_assignment_database_update(
                        assignment,
                        node["html_path"],
                        job_sync_id,
                        course_id
                    )
                
                all_assignments.extend(assignments)
                
            except Exception as e:
                print(f"Error processing {node['url']}: {e}")
        
        print(f"\nTotal assignments found: {len(all_assignments)}")
        return all_assignments
    
    async def handle_assignment_database_update(
        self,
        assignment: Assignment,
        html_path: str,
        job_sync_id: str,
        course_id: str = None
    ):
        """
        Handle database updates for assignments with source_page_paths logic
        """
        if not self.supabase:
            return
        
        try:
            if assignment.repeated:
                # Find existing assignment by title and description similarity
                existing_assignment = await self.find_existing_assignment(
                    assignment.title,
                    assignment.description
                )
                
                if existing_assignment:
                    # Get current source_page_paths
                    current_paths = existing_assignment.get("source_page_paths", []) or []
                    
                    # Add new html_path if not already present
                    if html_path not in current_paths:
                        updated_paths = current_paths + [html_path]
                        
                        # Update the assignment with new path
                        self.supabase.table("assignments")\
                            .update({"source_page_paths": updated_paths})\
                            .eq("id", existing_assignment["id"])\
                            .execute()
                        
                        print(f"    ✓ Updated existing assignment with new page path")
                    else:
                        print(f"    → Page path already exists for this assignment")
                else:
                    # Create new assignment even though marked as repeated
                    await self.create_new_assignment(assignment, html_path, job_sync_id, course_id)
            else:
                # Create new assignment
                await self.create_new_assignment(assignment, html_path, job_sync_id, course_id)
        
        except Exception as e:
            print(f"Error updating assignment database: {e}")
    
    async def find_existing_assignment(self, title: str, description: str) -> Optional[Dict]:
        """
        Find existing assignment by title/description similarity
        """
        try:
            # Simple exact match for now - could be enhanced with fuzzy matching
            result = self.supabase.table("assignments")\
                .select("*")\
                .eq("title", title)\
                .execute()
            
            if result.data:
                return result.data[0]
            
            return None
        except Exception as e:
            print(f"Error finding existing assignment: {e}")
            return None
    
    async def create_new_assignment(
        self,
        assignment: Assignment,
        html_path: str,
        job_sync_id: str,
        course_id: str = None
    ):
        """
        Create a new assignment with source_page_paths
        """
        try:
            assignment_data = {
                "title": assignment.title,
                "description": assignment.description,
                "content_hash": assignment.content_hash,
                "source_url": assignment.source_url,
                "source_page_paths": [html_path],
                "job_sync_id": job_sync_id,
                "course_id": course_id
            }
            
            result = self.supabase.table("assignments").insert(assignment_data).execute()
            
            if result.data:
                print(f"    ✓ Created new assignment: {assignment.title}")
            
        except Exception as e:
            print(f"Error creating new assignment: {e}")
