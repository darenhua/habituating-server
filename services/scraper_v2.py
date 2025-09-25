"""
Enhanced scraper with content hashing and change detection
"""
import asyncio
import hashlib
from typing import List, Optional, Set, Dict, Any
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright
from openai import AsyncOpenAI
from pydantic import BaseModel
from markdownify import markdownify
from urllib.parse import urljoin, urlparse
from dotenv import load_dotenv
import json
from supabase import create_client, Client
import os
from .utils.content_hasher import ContentHasher
from .utils.db_helpers import DbHelpers

load_dotenv()

class LinkAnalysis(BaseModel):
    relevant_links: List[str]
    assignment_found: bool
    reason: str

class Node:
    def __init__(self, url: str, parent: Optional["Node"] = None):
        self.url = url
        self.parent = parent
        self.children: List["Node"] = []
        self.assignment_data_found = False
        self.html_path: Optional[str] = None
        self.title = ""
        
        # New fields for idempotency
        self.content_hash: Optional[str] = None
        self.content_changed: bool = True  # Default to true for new content
        self.previous_hash: Optional[str] = None
        self.last_scraped: Optional[str] = None
    
    def is_leaf(self) -> bool:
        return len(self.children) == 0
    
    def add_child(self, url: str) -> "Node":
        child = Node(url, self)
        self.children.append(child)
        return child
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "assignment_data_found": self.assignment_data_found,
            "html_path": self.html_path,
            "content_hash": self.content_hash,
            "content_changed": self.content_changed,
            "previous_hash": self.previous_hash,
            "last_scraped": self.last_scraped,
            "children": [child.to_dict() for child in self.children],
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], parent: Optional["Node"] = None) -> "Node":
        node = cls(data["url"], parent)
        node.title = data.get("title", "")
        node.assignment_data_found = data.get("assignment_data_found", False)
        node.html_path = data.get("html_path")
        
        # Load new fields
        node.content_hash = data.get("content_hash")
        node.content_changed = data.get("content_changed", True)
        node.previous_hash = data.get("previous_hash")
        node.last_scraped = data.get("last_scraped")
        
        for child_data in data.get("children", []):
            child = Node.from_dict(child_data, node)
            node.children.append(child)
        
        return node

class ScraperV2:
    def __init__(self, supabase_client=None, job_sync_id: str = None):
        self.supabase = supabase_client
        self.job_sync_id = job_sync_id
        self.client = AsyncOpenAI()
        self.visited: Set[str] = set()
        self.storage_bucket = "scraped-html"
        self.content_hasher = ContentHasher()
    
    def resolve_url(self, base_url: str, link: str) -> str:
        """Resolve relative URLs to absolute URLs"""
        if not link:
            return ""
        
        link = link.strip().split("#")[0]
        
        if link.startswith(("http://", "https://")):
            return link
        
        if link.startswith("//"):
            parsed_base = urlparse(base_url)
            return f"{parsed_base.scheme}:{link}"
        
        return urljoin(base_url, link)
    
    async def save_html(self, url: str, html: str) -> str:
        """Save HTML to Supabase storage and return file path"""
        if not self.supabase or not self.job_sync_id:
            storage_dir = Path("storage")
            storage_dir.mkdir(exist_ok=True)
            filename = hashlib.md5(url.encode()).hexdigest() + ".html"
            path = storage_dir / filename
            path.write_text(html)
            return str(path)
        
        filename = f"{self.job_sync_id}/{hashlib.md5(url.encode()).hexdigest()}.html"
        html_bytes = html.encode("utf-8")
        
        try:
            response = self.supabase.storage.from_(self.storage_bucket).upload(
                filename,
                html_bytes,
                {
                    "content-type": "text/html",
                    "cache-control": "3600",
                    "upsert": "true",
                },
            )
            return filename
        except Exception as e:
            try:
                response = self.supabase.storage.from_(self.storage_bucket).update(
                    filename,
                    html_bytes,
                    {
                        "content-type": "text/html",
                        "cache-control": "3600",
                    },
                )
                return filename
            except Exception as update_error:
                print(f"Error uploading to storage: {e}, {update_error}")
                raise
    
    async def get_relevant_links(self, html: str, current_url: str) -> tuple[List[str], bool]:
        """Use LLM to find relevant links and check for assignment data"""
        markdown = markdownify(html, heading_style="closed")
        
        prompt = f"""Given this webpage for a distributed systems class, I need to:
1. Find links that might lead to homework/assignments
2. Check if this page contains assignment data with due dates

Current URL: {current_url}

Webpage content:
{markdown[:3000]}"""
        
        response = await self.client.responses.parse(
            model="gpt-4o-mini",
            input=[
                {
                    "role": "system",
                    "content": "You are analyzing a webpage to find homework/assignment related links and check for assignment data.",
                },
                {"role": "user", "content": prompt},
            ],
            text_format=LinkAnalysis,
        )
        
        result = response.output_parsed
        
        resolved_links = []
        for link in result.relevant_links:
            resolved = self.resolve_url(current_url, link)
            if resolved:
                resolved_links.append(resolved)
        
        return resolved_links, result.assignment_found
    
    async def scrape_page(self, page, url: str) -> tuple[str, str]:
        """Navigate to URL and get HTML + title"""
        await page.goto(url, wait_until="networkidle", timeout=30000)
        html = await page.content()
        title = await page.title()
        return html, title
    
    def clean_cookies_for_playwright(self, cookies):
        """Convert browser-exported cookies to Playwright format"""
        cleaned = []
        for cookie in cookies:
            clean_cookie = cookie.copy()
            
            if "sameSite" in clean_cookie:
                same_site = clean_cookie["sameSite"].lower()
                if same_site in ["unspecified", "no_restriction", ""]:
                    del clean_cookie["sameSite"]
                elif same_site == "none":
                    clean_cookie["sameSite"] = "None"
                elif same_site == "lax":
                    clean_cookie["sameSite"] = "Lax"
                elif same_site == "strict":
                    clean_cookie["sameSite"] = "Strict"
                else:
                    del clean_cookie["sameSite"]
            
            for field in ["hostOnly", "storeId", "session"]:
                clean_cookie.pop(field, None)
            
            cleaned.append(clean_cookie)
        
        return cleaned
    
    async def build_tree(
        self, 
        root_url: str, 
        cookies: List[Dict[str, Any]] = None,
        previous_tree: Optional[Dict] = None
    ) -> Node:
        """
        Build tree with content hashing and change detection
        """
        previous_hashes = {}
        if previous_tree:
            previous_hashes = DbHelpers.extract_hashes_from_tree(previous_tree)
            print(f"Found {len(previous_hashes)} pages from previous sync")
        
        root = Node(root_url)
        self.visited.add(root_url)
        
        queue = [(root, 0)]
        max_depth = 3
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            
            if cookies:
                await context.add_cookies(cookies)
            
            page = await context.new_page()
            
            while queue:
                current_level_nodes = []
                current_depth = queue[0][1] if queue else 0
                
                while queue and queue[0][1] == current_depth:
                    current_level_nodes.append(queue.pop(0)[0])
                
                for node in current_level_nodes:
                    try:
                        print(f"Processing level {current_depth}: {node.url}")
                        html, title = await self.scrape_page(page, node.url)
                        node.title = title
                        
                        # Generate content hash
                        node.content_hash = self.content_hasher.generate_content_hash(html, node.url)
                        node.last_scraped = datetime.now().isoformat()
                        
                        # Check if content changed
                        if node.url in previous_hashes:
                            node.previous_hash = previous_hashes[node.url]
                            node.content_changed = (node.content_hash != node.previous_hash)
                            
                            if not node.content_changed:
                                print(f"  ✓ Content unchanged: {node.url}")
                            else:
                                print(f"  ↻ Content changed: {node.url}")
                        else:
                            node.content_changed = True
                            print(f"  + New page: {node.url}")
                        
                        # Get relevant links and check for assignments
                        links, has_assignment = await self.get_relevant_links(html, node.url)
                        node.assignment_data_found = has_assignment
                        
                        # Always save HTML (for due date extraction)
                        node.html_path = await self.save_html(node.url, html)
                        
                        if has_assignment:
                            print(f"  📋 Has assignment data")
                        
                        # Add children
                        if current_depth < max_depth - 1:
                            for link in links:
                                if link not in self.visited:
                                    self.visited.add(link)
                                    child = node.add_child(link)
                                    queue.append((child, current_depth + 1))
                    
                    except Exception as e:
                        print(f"Error processing {node.url}: {e}")
            
            await browser.close()
        
        return root
    
    async def scrape_course_with_comparison(
        self,
        source_url: str,
        cookies: List[Dict[str, Any]] = None,
        previous_tree: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Main entry point for scraping with change detection"""
        cookies = self.clean_cookies_for_playwright(cookies) if cookies else []
        tree = await self.build_tree(source_url, cookies, previous_tree)
        
        # Generate summary statistics
        stats = self.generate_change_summary(tree)
        print("\n=== Scraping Summary ===")
        print(f"Total pages: {stats['total_pages']}")
        print(f"New pages: {stats['new_pages']}")
        print(f"Changed pages: {stats['changed_pages']}")
        print(f"Unchanged pages: {stats['unchanged_pages']}")
        print(f"Pages with assignments: {stats['pages_with_assignments']}")
        
        return tree.to_dict()
    
    def generate_change_summary(self, tree: Node) -> Dict:
        """Generate summary of changes in the tree"""
        stats = {
            "total_pages": 0,
            "new_pages": 0,
            "changed_pages": 0,
            "unchanged_pages": 0,
            "pages_with_assignments": 0,
            "pages_to_process": []
        }
        
        def analyze_node(node: Node):
            stats["total_pages"] += 1
            
            if node.assignment_data_found:
                stats["pages_with_assignments"] += 1
            
            if not node.previous_hash:
                stats["new_pages"] += 1
                if node.assignment_data_found:
                    stats["pages_to_process"].append(node.url)
            elif node.content_changed:
                stats["changed_pages"] += 1
                if node.assignment_data_found:
                    stats["pages_to_process"].append(node.url)
            else:
                stats["unchanged_pages"] += 1
            
            for child in node.children:
                analyze_node(child)
        
        analyze_node(tree)
        return stats