import asyncio
from typing import List, Optional, Set, Dict, Any
from playwright.async_api import async_playwright
from openai import AsyncOpenAI
from pydantic import BaseModel
from markdownify import markdownify
from pathlib import Path
import hashlib
from urllib.parse import urljoin, urlparse
from dotenv import load_dotenv
import json

load_dotenv()


class LinkAnalysis(BaseModel):
    relevant_links: List[str]
    assignment_found: bool
    reason: str


cookies = []


class Node:
    def __init__(self, url: str, parent: Optional["Node"] = None):
        self.url = url
        self.parent = parent
        self.children: List["Node"] = []
        self.assignment_data_found = False
        self.html_path: Optional[str] = None
        self.title = ""

    def is_leaf(self) -> bool:
        return len(self.children) == 0

    def add_child(self, url: str) -> "Node":
        child = Node(url, self)
        self.children.append(child)
        return child

    def to_dict(self) -> Dict[str, Any]:
        """Convert node to dictionary for JSON serialization"""
        return {
            "url": self.url,
            "title": self.title,
            "assignment_data_found": self.assignment_data_found,
            "html_path": self.html_path,
            "children": [child.to_dict() for child in self.children],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], parent: Optional["Node"] = None) -> "Node":
        """Reconstruct Node from dictionary"""
        node = cls(data["url"], parent)
        node.title = data["title"]
        node.assignment_data_found = data["assignment_data_found"]
        node.html_path = data["html_path"]

        # Recursively create children
        for child_data in data["children"]:
            child = Node.from_dict(child_data, node)
            node.children.append(child)

        return node


class Scraper:
    def __init__(self, storage_dir: str = "storage", openai_api_key: str = None):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
        self.client = AsyncOpenAI()
        self.visited: Set[str] = set()

    def resolve_url(self, base_url: str, link: str) -> str:
        """Resolve relative URLs to absolute URLs"""
        # Handle None or empty links
        if not link:
            return ""

        # Remove whitespace and fragments
        link = link.strip().split("#")[0]

        # Handle different link types:
        # 1. Absolute URLs (http://, https://)
        if link.startswith(("http://", "https://")):
            return link

        # 2. Protocol-relative URLs (//example.com)
        if link.startswith("//"):
            parsed_base = urlparse(base_url)
            return f"{parsed_base.scheme}:{link}"

        # 3. Relative URLs - use urljoin to handle all cases
        # This handles: /path, ./path, ../path, path
        return urljoin(base_url, link)

    async def save_html(self, url: str, html: str) -> str:
        """Save HTML to storage and return file path"""
        filename = hashlib.md5(url.encode()).hexdigest() + ".html"
        path = self.storage_dir / filename
        path.write_text(html)
        return str(path)

    async def get_relevant_links(
        self, html: str, current_url: str
    ) -> tuple[List[str], bool]:
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

        # Resolve all relative URLs to absolute URLs
        resolved_links = []
        for link in result.relevant_links:
            resolved = self.resolve_url(current_url, link)
            if resolved:  # Only add non-empty URLs
                resolved_links.append(resolved)

        return resolved_links, result.assignment_found

    async def scrape_page(self, page, url: str) -> tuple[str, str]:
        """Navigate to URL and get HTML + title"""
        await page.goto(url, wait_until="networkidle", timeout=30000)
        html = await page.content()
        title = await page.title()
        return html, title

    async def build_tree(self, root_url: str) -> Node:
        """Build tree starting from root URL using breadth-first search"""
        root = Node(root_url)
        self.visited.add(root_url)

        # Queue for BFS: list of (node, depth) tuples
        queue = [(root, 0)]
        max_depth = 3  # Limit tree depth

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()

            while queue:
                current_level_nodes = []
                current_depth = queue[0][1] if queue else 0

                # Collect all nodes at current depth
                while queue and queue[0][1] == current_depth:
                    current_level_nodes.append(queue.pop(0)[0])

                # Process all nodes at current level
                for node in current_level_nodes:
                    try:
                        print(f"Processing level {current_depth}: {node.url}")
                        html, title = await self.scrape_page(page, node.url)
                        node.title = title

                        # Get relevant links and check for assignments
                        links, has_assignment = await self.get_relevant_links(
                            html, node.url
                        )
                        node.assignment_data_found = has_assignment

                        # Save HTML only if assignment data found
                        if has_assignment:
                            node.html_path = await self.save_html(node.url, html)
                            print(f"Found assignment data at: {node.url}")

                        # Add unvisited links to queue for next level
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


async def main():
    scraper = Scraper()
    tree = await scraper.build_tree("https://systems.cs.columbia.edu/ds1-class/")

    # Print tree
    def print_tree(node: Node, indent: int = 0):
        prefix = "  " * indent + "├─ "
        status = "📅" if node.assignment_data_found else ""
        print(f"{prefix}{node.title} {status}")
        for child in node.children:
            print_tree(child, indent + 1)

    print_tree(tree)

    # Export tree to JSON
    tree_dict = tree.to_dict()
    json_filename = "scraped_tree.json"

    with open(json_filename, "w", encoding="utf-8") as f:
        json.dump(tree_dict, f, indent=2, ensure_ascii=False)

    print(f"\nTree exported to {json_filename}")


if __name__ == "__main__":
    asyncio.run(main())
