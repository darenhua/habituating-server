from pydantic import BaseModel, Field, HttpUrl, field_validator
from typing import List, Optional, Set, Dict
from datetime import datetime
from playwright.sync_api import sync_playwright
import json

cookies = []


class URLNode(BaseModel):
    """Represents a single URL node in the tree structure."""

    url: HttpUrl
    title: Optional[str] = None
    parent_url: Optional[HttpUrl] = None
    children: List["URLNode"] = Field(default_factory=list)

    @field_validator("url")
    @classmethod
    def validate_url(cls, v):
        """Ensure URL is properly formatted."""
        return str(v).rstrip("/")

    def add_child(self, child_node: "URLNode") -> None:
        """Add a child node to this node."""
        child_node.parent_url = self.url
        self.children.append(child_node)

    def get_all_urls(self) -> Set[str]:
        """Recursively get all URLs in the tree starting from this node."""
        urls = {str(self.url)}
        for child in self.children:
            urls.update(child.get_all_urls())
        return urls

    def to_dict(self, include_children: bool = True) -> Dict:
        """Convert node to dictionary representation."""
        data = {
            "url": str(self.url),
            "title": self.title,
            "parent_url": str(self.parent_url) if self.parent_url else None,
        }
        if include_children:
            data["children"] = [child.to_dict() for child in self.children]
        return data

    def print_tree(self, indent: int = 0) -> None:
        """Print the tree structure in a readable format."""
        prefix = "  " * indent + "├─ " if indent > 0 else ""
        print(f"{prefix}{self.title or 'Untitled'} - {self.url}")
        for child in self.children:
            child.print_tree(indent + 1)


class URLTree(BaseModel):
    """Main tree structure for organizing scraped URLs."""

    root: URLNode
    max_depth: int = 3
    max_children_per_node: int = 50
    visited_urls: Set[str] = Field(default_factory=set)
    domain_restriction: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True

    def should_visit_url(self, url: str) -> bool:
        """Check if a URL should be visited based on tree rules."""
        # Already visited
        if url in self.visited_urls:
            return False

        # Domain restriction
        if self.domain_restriction:
            parsed = urlparse(url)
            if parsed.netloc != self.domain_restriction:
                return False

        return True

    def mark_visited(self, url: str) -> None:
        """Mark a URL as visited."""
        self.visited_urls.add(url.rstrip("/"))


class WebScraper:
    """Async web scraper that builds a URL tree structure."""
    
    def __init__(
        self,
        max_depth: int = 3,
        max_children_per_node: int = 50,
        same_domain_only: bool = True,
        timeout: int = 10,
        max_concurrent: int = 5
    ):
        self.max_depth = max_depth
        self.max_children_per_node = max_children_per_node
        self.same_domain_only = same_domain_only
        self.timeout = timeout
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def fetch_page(self, session: aiohttp.ClientSession, url: str) -> tuple[Optional[str], Optional[str], int]:
        """Fetch a single page and return its HTML content, title, and status code."""
        try:
            async with self.semaphore:
                async with session.get(url, timeout=self.timeout) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        title = soup.find('title')
                        return html, title.text.strip() if title else None, response.status
                    return None, None, response.status
        except asyncio.TimeoutError:
            return None, None, -1
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None, None, -2
    
    def extract_links(self, html: str, base_url: str) -> List[str]:
        """Extract all links from HTML content."""
        soup = BeautifulSoup(html, 'html.parser')
        links = []
        
        for tag in soup.find_all(['a', 'link']):
            href = tag.get('href')
            if href:
                # Convert relative URLs to absolute
                absolute_url = urljoin(base_url, href)
                
                # Parse and clean the URL
                parsed = urlparse(absolute_url)
                
                # Skip non-HTTP(S) protocols, fragments, and certain file types
                if parsed.scheme not in ['http', 'https']:
                    continue
                if parsed.path.endswith(('.pdf', '.zip', '.exe', '.dmg', '.jpg', '.png', '.gif')):
                    continue
                
                # Remove fragment and reconstruct URL
                clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                if parsed.query:
                    clean_url += f"?{parsed.query}"
                
                links.append(clean_url.rstrip('/'))
        
        return list(set(links))  # Remove duplicates
    
    async def scrape_node(
        self,
        session: aiohttp.ClientSession,
        node: URLNode,
        tree: URLTree
    ) -> None:
        """Scrape a single node and its children."""
        if node.depth >= self.max_depth:
            return
        
        url = str(node.url)
        
        # Fetch the page
        html, title, status_code = await self.fetch_page(session, url)
        
        # Update node information
        node.visited_at = datetime.now()
        node.title = title
        node.status_code = status_code
        
        if html:
            # Calculate content hash for duplicate detection
            node.content_hash = hashlib.md5(html.encode()).hexdigest()
            
            # Extract links
            links = self.extract_links(html, url)
            
            # Filter and limit links
            valid_links = []
            for link in links:
                if tree.should_visit_url(link):
                    valid_links.append(link)
                    if len(valid_links) >= self.max_children_per_node:
                        break
            
            # Create child nodes
            child_tasks = []
            for link in valid_links:
                tree.mark_visited(link)
                child_node = URLNode(url=link)
                node.add_child(child_node)
                child_tasks.append(self.scrape_node(session, child_node, tree))
            
            # Recursively scrape children
            if child_tasks:
                await asyncio.gather(*child_tasks, return_exceptions=True)
        else:
            node.error = f"Failed to fetch: Status {status_code}"
    
    async def build_tree(self, root_url: str) -> URLTree:
        """Build the complete URL tree starting from a root URL."""
        # Parse root URL for domain restriction
        parsed_root = urlparse(root_url)
        domain = parsed_root.netloc if self.same_domain_only else None
        
        # Initialize tree
        root_node = URLNode(url=root_url)
        tree = URLTree(
            root=root_node,
            max_depth=self.max_depth,
            max_children_per_node=self.max_children_per_node,
            domain_restriction=domain
        )
        tree.mark_visited(root_url)
        
        # Start scraping
        connector = aiohttp.TCPConnector(limit=30)
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; URLTreeBot/1.0)'}
        ) as session:
            await self.scrape_node(session, root_node, tree)
        
        return tree




def clean_cookies_for_playwright(cookies):
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


def use_canvas_session():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        cleaned_cookies = clean_cookies_for_playwright(cookies)
        context.add_cookies(cleaned_cookies)

        page = context.new_page()

        page.goto("https://courseworks2.columbia.edu/courses/227015")

        page.screenshot(path="victim_logged_in.png")


if __name__ == "__main__":
    use_canvas_session()
