"""
Database helper functions for idempotent operations
"""
from typing import Dict, List, Optional, Any
from supabase import Client

class DbHelpers:
    @staticmethod
    def get_previous_tree(supabase: Client, course_id: str, current_sync_id: str) -> Optional[Dict]:
        """Get the most recent previous scraped tree for a course"""
        result = (
            supabase.table("job_syncs")
            .select("scraped_tree")
            .eq("course_id", course_id)
            .neq("id", current_sync_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return result.data[0].get("scraped_tree") if result.data else None
    
    @staticmethod
    def get_assignments_by_content_hash(supabase: Client, content_hash: str) -> List[Dict]:
        """Get all assignments associated with a specific page content hash"""
        result = (
            supabase.table("assignments")
            .select("*")
            .eq("content_hash", content_hash)
            .execute()
        )
        return result.data if result.data else []
    
    @staticmethod
    def assignment_exists(supabase: Client, content_hash: str, title: str) -> bool:
        """Check if an assignment already exists with the same content hash and title"""
        result = (
            supabase.table("assignments")
            .select("id")
            .eq("content_hash", content_hash)
            .eq("title", title)
            .limit(1)
            .execute()
        )
        return len(result.data) > 0 if result.data else False
    
    @staticmethod
    def extract_hashes_from_tree(tree: Dict) -> Dict[str, str]:
        """Extract URL -> content_hash mapping from a tree"""
        hash_map = {}
        
        def traverse(node):
            if node.get("content_hash"):
                hash_map[node["url"]] = node["content_hash"]
            for child in node.get("children", []):
                traverse(child)
        
        traverse(tree)
        return hash_map