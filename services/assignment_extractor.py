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
try:
    from services.utils.db_helpers import DbHelpers
except ImportError:
    from utils.db_helpers import DbHelpers
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
        
        # Collect all nodes with assignments
        nodes_to_process = []
        
        def collect_nodes(node: Dict):
            if node.get("assignment_data_found"):
                nodes_to_process.append(node)
            for child in node.get("children", []):
                collect_nodes(child)
        
        collect_nodes(scraped_tree)
        
        print(f"\n=== Assignment Extraction ===")
        print(f"Found {len(nodes_to_process)} pages with potential assignments")
        
        # Get ALL previous assignments for this course to provide full context
        course_base_url = scraped_tree.get("url", "")
        all_previous_assignments = []
        if self.supabase and course_base_url:
            all_previous_assignments = DbHelpers.get_all_assignments_for_course(
                self.supabase,
                course_base_url
            )
            print(f"Found {len(all_previous_assignments)} previous assignments for context")
        
        # Process each page
        for node in nodes_to_process:
            try:
                # For unchanged pages, we can skip or retrieve from DB
                if not node.get("content_changed", True):
                    print(f"✓ Page unchanged: {node['url']}")
                    
                    # Try to get existing assignments from database
                    if self.supabase:
                        existing = DbHelpers.get_assignments_by_content_hash(
                            self.supabase,
                            node["content_hash"]
                        )
                        
                        if existing:
                            # Convert to Assignment objects
                            for assignment_data in existing:
                                assignment = Assignment(
                                    title=assignment_data["title"],
                                    description=assignment_data["description"],
                                    repeated=assignment_data.get("repeated", False),
                                    content_hash=assignment_data["content_hash"],
                                    source_url=assignment_data.get("source_url", node["url"])
                                )
                                all_assignments.append(assignment)
                            print(f"  Retrieved {len(existing)} assignments from database")
                            continue
                        else:
                            print(f"  No assignments in database, re-extracting...")
                    else:
                        print(f"  No database connection, re-extracting...")
                
                print(f"↻ Processing page: {node['url']}")
                
                # Extract assignments using ALL course assignments for context
                assignments = await self.extract_assignments_from_page(
                    node,
                    all_previous_assignments
                )
                
                print(f"  Found {len(assignments)} assignments")
                all_assignments.extend(assignments)
                
            except Exception as e:
                print(f"Error processing {node['url']}: {e}")
        
        print(f"\nTotal assignments found: {len(all_assignments)}")
        return all_assignments
    
