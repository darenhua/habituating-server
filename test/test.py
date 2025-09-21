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
from supabase import create_client, Client
import os

load_dotenv()


class LinkAnalysis(BaseModel):
    relevant_links: List[str]
    assignment_found: bool
    reason: str


cookies = [
    {
        "domain": "courseworks2.columbia.edu",
        "hostOnly": True,
        "httpOnly": True,
        "name": "_legacy_normandy_session",
        "path": "/",
        "sameSite": "unspecified",
        "secure": True,
        "session": True,
        "storeId": "0",
        "value": "588Kut7xQ0J_uKMUwRdLoQ+cUlX_y02FiIup8Oh_t_2ZYeRNxgrZkCDgDCkokBU_9LT8kysh5a65fgcqUkxWDDs7xhECYxkgYy_ECcRI9pgeusMk0IjGfFr1iihsYfoKY_vYBi2-OTonjwDHan-Izbs4xWV4UdfnFDS0K-3EHoberFw-0J2A0rRQ2bGjaSIHfhzdDaKvqpbocf1BWFyeGvllCrPdBS3KuGV46jRLQ49WJwXiUe3JFnHUFnc_OwSwfba1kPs2HIAtp68fHHVpG0kkQUsqPsSSo933QM2IaRpZ77HWkjsYdx3ytSZ1fU03_n_c8UHS-7b8NRqpllHWedXxxB34J3fj2EMOvyXSgfBuUb4GbzrmrvjotNNV-eVh8MxcMiZ7VgUic4lg090l9YSAT7SQ96MWbkePmMwUQgSj-sObwMDM-fkmmdoT0rku8ST-UAXKnvUp4pUs6SR72NDl-BBsmUoucpraXaO4trRzgA8HSUTMizx-L2H8lxirEpMhCz6E0IFivYMTBkh39fv.D6oYLO1z8UDZ47AjNWEqYWPC_oQ.aMHbKw",
    },
    {
        "domain": "courseworks2.columbia.edu",
        "hostOnly": True,
        "httpOnly": True,
        "name": "log_session_id",
        "path": "/",
        "sameSite": "unspecified",
        "secure": True,
        "session": True,
        "storeId": "0",
        "value": "dedc7de91b5c9ba7870192b941fb2e4f",
    },
    {
        "domain": "courseworks2.columbia.edu",
        "hostOnly": True,
        "httpOnly": True,
        "name": "canvas_session",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": True,
        "storeId": "0",
        "value": "eWwDT879gUl-wVT_du_8Lg+yKXHM4JmxtyQW4VszCu-nf9gk__PGr7lX6yUS8LSHtdc20B4aaJNDiSMUQhf6fBUU_zBtzQAD4mkXlzvgmjO2RmaMxiMth6F7K5KY-l-rKaNMi4-paJVNZ1-n6YTVT4vA_3wTsDHE4PBD-soqvdRtLjs3437a0K-sHiX0-gsyJDTAdL11v1zoEVMHrSwVq5032mP-2TWHQ2-ZbkOA2eqVS-ynGC7dq2z06E6vqTYhrFp6IiEvui7FrRvmTqJanodZ7uSWhg0S0ZXMsU7LbTnEooFsxOJCaIorILAEcd94l_faawecUsC5hYHoNI-TZPzV2RSb6YjgcBE7pEPsdn1OOOLDGVtbL8cLEdxHDOCMBMMCkRRWj3YSOfVW2MSpO4FGxyTXogWBiOXsxQZOEZqnly26_7kVxrWX3bPnd5jqgW_NF3Iu1Pjn4WZMaIQl3jrnD8njerzZlbFMHs9rVOAfA.Uy1egIHR12n36ahQyG3iTGI16sU.aM9X2g",
    },
    {
        "domain": "courseworks2.columbia.edu",
        "hostOnly": True,
        "httpOnly": False,
        "name": "_csrf_token",
        "path": "/",
        "sameSite": "unspecified",
        "secure": True,
        "session": True,
        "storeId": "0",
        "value": "bWF7Wu%2Bedx2H6GotaXIbPoXBf8qf07IakDXz35KkziAjEwoInNYySvCrPEcnB3UHz60Xvtiag1%2FeRMSL4pSecg%3D%3D",
    },
]


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
    def __init__(self, supabase_client=None, job_sync_id: str = None):
        self.supabase = supabase_client
        self.job_sync_id = job_sync_id
        self.client = AsyncOpenAI()
        self.visited: Set[str] = set()
        self.storage_bucket = "scraped-html"

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
        """Save HTML to Supabase storage and return file path"""
        if not self.supabase or not self.job_sync_id:
            # Fallback to local storage for backward compatibility
            storage_dir = Path("storage")
            storage_dir.mkdir(exist_ok=True)
            filename = hashlib.md5(url.encode()).hexdigest() + ".html"
            path = storage_dir / filename
            path.write_text(html)
            return str(path)

        filename = f"{self.job_sync_id}/{hashlib.md5(url.encode()).hexdigest()}.html"

        # Convert string to bytes
        html_bytes = html.encode("utf-8")

        # Upload to Supabase storage
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
            # Try to update if file exists
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

    async def build_tree(
        self, root_url: str, cookies: List[Dict[str, Any]] = None
    ) -> Node:
        """Build tree starting from root URL using breadth-first search"""
        root = Node(root_url)
        self.visited.add(root_url)

        # Queue for BFS: list of (node, depth) tuples
        queue = [(root, 0)]
        max_depth = 3  # Limit tree depth

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()

            # Add cookies if provided
            if cookies:
                await context.add_cookies(cookies)

            page = await context.new_page()

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

    def clean_cookies_for_playwright(self, cookies):
        """Convert browser-exported cookies to Playwright format"""
        cleaned = []
        for cookie in cookies:
            # Create a copy to avoid modifying original
            clean_cookie = cookie.copy()

            # Handle sameSite conversion
            if "sameSite" in clean_cookie:
                same_site = clean_cookie["sameSite"].lower()
                if same_site in ["unspecified", "no_restriction", ""]:
                    # "unspecified" usually means no sameSite was set
                    # In Playwright, omit it or use "Lax" as default
                    del clean_cookie["sameSite"]
                elif same_site == "none":
                    clean_cookie["sameSite"] = "None"
                elif same_site == "lax":
                    clean_cookie["sameSite"] = "Lax"
                elif same_site == "strict":
                    clean_cookie["sameSite"] = "Strict"
                else:
                    # Remove invalid values
                    del clean_cookie["sameSite"]

            # Remove browser-specific fields that Playwright doesn't use
            for field in ["hostOnly", "storeId", "session"]:
                clean_cookie.pop(field, None)

            cleaned.append(clean_cookie)

        return cleaned

    async def scrape_course(
        self, source_url: str, cookies: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Scrape a course URL and return the tree structure as a dictionary"""
        cookies = self.clean_cookies_for_playwright(cookies)
        tree = await self.build_tree(source_url, cookies)
        return tree.to_dict()


async def main():
    # Example usage for testing
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    scraper = Scraper(supabase_client=supabase, job_sync_id="123")
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
