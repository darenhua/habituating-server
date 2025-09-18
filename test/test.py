import asyncio
import json
from typing import List, Optional, Set
from playwright.async_api import async_playwright
from openai import AsyncOpenAI
from markdownify import markdownify
from pathlib import Path
import hashlib
from dotenv import load_dotenv

load_dotenv()


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


class Scraper:
    def __init__(self, storage_dir: str = "storage", openai_api_key: str = None):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
        self.client = AsyncOpenAI()
        self.visited: Set[str] = set()

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
{markdown[:3000]}

Return JSON with:
- "relevant_links": list of URLs to follow (assignment/homework related)
- "assignment_found": true if this page has assignment info with due dates
- "reason": brief explanation"""

        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )

        data = json.loads(response.choices[0].message.content)
        return data.get("relevant_links", []), data.get("assignment_found", False)

    async def scrape_page(self, page, url: str) -> tuple[str, str]:
        """Navigate to URL and get HTML + title"""
        await page.goto(url, wait_until="networkidle", timeout=30000)
        html = await page.content()
        title = await page.title()
        return html, title

    async def build_tree(self, root_url: str) -> Node:
        """Build tree starting from root URL"""
        root = Node(root_url)
        self.visited.add(root_url)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()

            async def process_node(node: Node):
                try:
                    html, title = await self.scrape_page(page, node.url)
                    node.title = title

                    # Save HTML
                    node.html_path = await self.save_html(node.url, html)

                    # Get relevant links and check for assignments
                    links, has_assignment = await self.get_relevant_links(
                        html, node.url
                    )
                    node.assignment_data_found = has_assignment

                    # Process unvisited links
                    for link in links:
                        if link not in self.visited:
                            self.visited.add(link)
                            child = node.add_child(link)
                            await process_node(child)

                except Exception as e:
                    print(f"Error processing {node.url}: {e}")

            await process_node(root)
            await browser.close()

        return root


async def main():
    scraper = Scraper(openai_api_key="your-api-key-here")
    tree = await scraper.build_tree("https://systems.cs.columbia.edu/ds1-class/")

    # Print tree
    def print_tree(node: Node, indent: int = 0):
        prefix = "  " * indent + "├─ "
        status = "📅" if node.assignment_data_found else ""
        print(f"{prefix}{node.title} {status}")
        for child in node.children:
            print_tree(child, indent + 1)

    print_tree(tree)


if __name__ == "__main__":
    asyncio.run(main())
