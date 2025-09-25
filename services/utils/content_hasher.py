"""
Content hashing utilities for stable page identification
"""
import hashlib
from bs4 import BeautifulSoup
from typing import Optional

class ContentHasher:
    @staticmethod
    def generate_content_hash(html: str, url: str) -> str:
        """
        Generate stable hash from HTML content using text-only extraction.
        This is immune to HTML structure changes while capturing content changes.
        """
        # Parse HTML
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove non-content elements
        for element in soup(['script', 'style', 'meta', 'link', 'noscript', 'header', 'footer', 'nav']):
            element.decompose()
        
        # Extract text
        text = soup.get_text(separator=' ', strip=True)
        
        # Normalize whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        normalized_text = ' '.join(chunk for chunk in chunks if chunk)
        
        # Convert to lowercase for consistency
        normalized_text = ' '.join(normalized_text.lower().split())
        
        # Create hash with URL for uniqueness
        content_to_hash = f"{url}|{normalized_text}"
        return hashlib.sha256(content_to_hash.encode('utf-8')).hexdigest()
    
    @staticmethod
    def has_content_changed(current_hash: str, previous_hash: Optional[str]) -> bool:
        """Check if content has changed based on hash comparison"""
        if previous_hash is None:
            return True  # New content
        return current_hash != previous_hash