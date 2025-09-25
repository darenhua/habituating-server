"""
Test script to verify idempotent scraper functionality
"""
import asyncio
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client
import sys

# Add parent directory to path to import services
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.scraper_v2 import ScraperV2
from services.utils.content_hasher import ContentHasher
from services.utils.db_helpers import DbHelpers

load_dotenv()

# Test cookies (you can update these with fresh ones if needed)
cookies = [
    {
        "domain": "courseworks2.columbia.edu",
        "httpOnly": True,
        "name": "_legacy_normandy_session",
        "path": "/",
        "secure": True,
        "value": "588Kut7xQ0J_uKMUwRdLoQ+cUlX_y02FiIup8Oh_t_2ZYeRNxgrZkCDgDCkokBU_9LT8kysh5a65fgcqUkxWDDs7xhECYxkgYy_ECcRI9pgeusMk0IjGfFr1iihsYfoKY_vYBi2-OTonjwDHan-Izbs4xWV4UdfnFDS0K-3EHoberFw-0J2A0rRQ2bGjaSIHfhzdDaKvqpbocf1BWFyeGvllCrPdBS3KuGV46jRLQ49WJwXiUe3JFnHUFnc_OwSwfba1kPs2HIAtp68fHHVpG0kkQUsqPsSSo933QM2IaRpZ77HWkjsYdx3ytSZ1fU03_n_c8UHS-7b8NRqpllHWedXxxB34J3fj2EMOvyXSgfBuUb4GbzrmrvjotNNV-eVh8MxcMiZ7VgUic4lg090l9YSAT7SQ96MWbkePmMwUQgSj-sObwMDM-fkmmdoT0rku8ST-UAXKnvUp4pUs6SR72NDl-BBsmUoucpraXaO4trRzgA8HSUTMizx-L2H8lxirEpMhCz6E0IFivYMTBkh39fv.D6oYLO1z8UDZ47AjNWEqYWPC_oQ.aMHbKw",
    },
    {
        "domain": "courseworks2.columbia.edu",
        "httpOnly": True,
        "name": "log_session_id",
        "path": "/",
        "secure": True,
        "value": "dedc7de91b5c9ba7870192b941fb2e4f",
    },
    {
        "domain": "courseworks2.columbia.edu",
        "httpOnly": True,
        "name": "canvas_session",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "value": "eWwDT879gUl-wVT_du_8Lg+yKXHM4JmxtyQW4VszCu-nf9gk__PGr7lX6yUS8LSHtdc20B4aaJNDiSMUQhf6fBUU_zBtzQAD4mkXlzvgmjO2RmaMxiMth6F7K5KY-l-rKaNMi4-paJVNZ1-n6YTVT4vA_3wTsDHE4PBD-soqvdRtLjs3437a0K-sHiX0-gsyJDTAdL11v1zoEVMHrSwVq5032mP-2TWHQ2-ZbkOA2eqVS-ynGC7dq2z06E6vqTYhrFp6IiEvui7FrRvmTqJanodZ7uSWhg0S0ZXMsU7LbTnEooFsxOJCaIorILAEcd94l_faawecUsC5hYHoNI-TZPzV2RSb6YjgcBE7pEPsdn1OOOLDGVtbL8cLEdxHDOCMBMMCkRRWj3YSOfVW2MSpO4FGxyTXogWBiOXsxQZOEZqnly26_7kVxrWX3bPnd5jqgW_NF3Iu1Pjn4WZMaIQl3jrnD8njerzZlbFMHs9rVOAfA.Uy1egIHR12n36ahQyG3iTGI16sU.aM9X2g",
    },
    {
        "domain": "courseworks2.columbia.edu",
        "httpOnly": False,
        "name": "_csrf_token",
        "path": "/",
        "secure": True,
        "value": "bWF7Wu%2Bedx2H6GotaXIbPoXBf8qf07IakDXz35KkziAjEwoInNYySvCrPEcnB3UHz60Xvtiag1%2FeRMSL4pSecg%3D%3D",
    },
]

async def test_content_hasher():
    """Test the content hashing functionality"""
    print("\n=== Testing Content Hasher ===")
    hasher = ContentHasher()
    
    # Test with sample HTML
    html1 = """
    <html>
        <head><title>Test Page</title></head>
        <body>
            <h1>Assignment 1</h1>
            <p>Due date: October 15, 2024</p>
        </body>
    </html>
    """
    
    html2 = """
    <html>
        <head><title>Test Page</title></head>
        <body>
            <h1>Assignment 1</h1>
            <p>Due date: October 16, 2024</p>  <!-- Changed date -->
        </body>
    </html>
    """
    
    html3 = """
    <html>
        <head><title>Test Page</title>
        <style>body { color: red; }</style>  <!-- Only style changed -->
        </head>
        <body>
            <h1>Assignment 1</h1>
            <p>Due date: October 15, 2024</p>
        </body>
    </html>
    """
    
    url = "https://example.com/test"
    
    hash1 = hasher.generate_content_hash(html1, url)
    hash2 = hasher.generate_content_hash(html2, url)
    hash3 = hasher.generate_content_hash(html3, url)
    
    print(f"Hash 1: {hash1[:16]}...")
    print(f"Hash 2: {hash2[:16]}...")
    print(f"Hash 3: {hash3[:16]}...")
    
    print(f"\nContent changed (html1 vs html2): {hasher.has_content_changed(hash2, hash1)}")
    print(f"Content changed (html1 vs html3): {hasher.has_content_changed(hash3, hash1)}")
    
    assert hash1 != hash2, "Hashes should differ when content changes"
    assert hash1 == hash3, "Hashes should be same when only style changes"
    print("✅ Content hasher tests passed!")

async def test_scraper_local():
    """Test scraper with local/mock data (no Supabase)"""
    print("\n=== Testing Scraper (Local Mode) ===")
    
    # For local testing, you can use a simple test URL or mock the scraping
    test_url = "https://systems.cs.columbia.edu/ds1-class/"
    
    print("\n1. First scrape (no previous data)...")
    # Note: This would need actual browser automation to work
    # For testing without browser, we'll simulate the tree structure
    
    # Create a simulated tree for testing
    from services.scraper_v2 import Node
    
    root = Node(test_url)
    root.title = "Test Course"
    root.content_hash = "hash123"
    root.content_changed = True
    root.assignment_data_found = True
    
    child1 = root.add_child("https://example.com/hw1")
    child1.title = "Homework 1"
    child1.content_hash = "hash456"
    child1.content_changed = True
    child1.assignment_data_found = True
    
    tree_dict = root.to_dict()
    
    # Save the tree for comparison
    with open("test_tree_v1.json", "w") as f:
        json.dump(tree_dict, f, indent=2)
    
    print("First scrape complete. Tree saved to test_tree_v1.json")
    
    # Simulate second scrape with previous data
    print("\n2. Second scrape (with previous data)...")
    
    # Load previous tree
    with open("test_tree_v1.json", "r") as f:
        previous_tree = json.load(f)
    
    # Extract hashes from previous tree
    previous_hashes = DbHelpers.extract_hashes_from_tree(previous_tree)
    print(f"Found {len(previous_hashes)} pages from previous sync")
    
    for url, hash_val in previous_hashes.items():
        print(f"  - {url}: {hash_val[:16]}...")
    
    # Simulate a second scrape where some content changed
    root2 = Node(test_url)
    root2.title = "Test Course"
    root2.content_hash = "hash123"  # Same hash - no change
    root2.previous_hash = previous_hashes.get(test_url)
    root2.content_changed = False
    root2.assignment_data_found = True
    
    child2 = root2.add_child("https://example.com/hw1")
    child2.title = "Homework 1 - Updated"
    child2.content_hash = "hash789"  # Different hash - content changed
    child2.previous_hash = previous_hashes.get("https://example.com/hw1")
    child2.content_changed = True
    child2.assignment_data_found = True
    
    # Add a new page
    child3 = root2.add_child("https://example.com/hw2")
    child3.title = "Homework 2"
    child3.content_hash = "hash999"
    child3.content_changed = True  # New page
    child3.assignment_data_found = True
    
    tree_dict2 = root2.to_dict()
    
    # Save the second tree
    with open("test_tree_v2.json", "w") as f:
        json.dump(tree_dict2, f, indent=2)
    
    print("Second scrape complete. Tree saved to test_tree_v2.json")
    
    # Generate change summary (no need to instantiate ScraperV2 here)
    from services.scraper_v2 import ScraperV2 as ScraperClass
    stats = ScraperClass().generate_change_summary(root2)
    
    print("\n=== Change Summary ===")
    print(f"Total pages: {stats['total_pages']}")
    print(f"New pages: {stats['new_pages']}")
    print(f"Changed pages: {stats['changed_pages']}")
    print(f"Unchanged pages: {stats['unchanged_pages']}")
    print(f"Pages with assignments: {stats['pages_with_assignments']}")
    print(f"Pages to process: {stats['pages_to_process']}")
    
    print("\n✅ Local scraper test complete!")

async def test_scraper_with_browser():
    """Test the actual scraper with browser automation"""
    print("\n=== Testing Scraper with Browser (Live) ===")
    print("NOTE: This requires valid cookies and will open a browser window")
    
    # Initialize Supabase if available
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    
    if SUPABASE_URL and SUPABASE_KEY:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        scraper = ScraperV2(supabase_client=supabase, job_sync_id="test_123")
        print("Using Supabase storage")
    else:
        scraper = ScraperV2()
        print("Using local storage")
    
    # Test URL - you can change this to test different sites
    test_url = "https://systems.cs.columbia.edu/ds1-class/"
    
    # First run - no previous data
    print("\n1. First scrape...")
    # Don't use courseworks cookies for systems.cs.columbia.edu
    tree_dict1 = await scraper.scrape_course_with_comparison(
        test_url,
        cookies=None,  # No cookies needed for public site
        previous_tree=None
    )
    
    # Save first tree
    with open("live_tree_v1.json", "w") as f:
        json.dump(tree_dict1, f, indent=2)
    print("First scrape saved to live_tree_v1.json")
    
    # Second run - with previous data (simulating idempotency)
    print("\n2. Second scrape (testing idempotency)...")
    scraper2 = ScraperV2(supabase_client=supabase if SUPABASE_URL else None, job_sync_id="test_124")
    tree_dict2 = await scraper2.scrape_course_with_comparison(
        test_url,
        cookies=None,  # No cookies needed for public site
        previous_tree=tree_dict1  # Pass previous tree for comparison
    )
    
    # Save second tree
    with open("live_tree_v2.json", "w") as f:
        json.dump(tree_dict2, f, indent=2)
    print("Second scrape saved to live_tree_v2.json")
    
    print("\n✅ Live scraper test complete!")
    print("Check the JSON files to see the content hashes and change detection in action")

async def main():
    """Main test runner"""
    print("=" * 60)
    print("IDEMPOTENT SCRAPER TEST SUITE")
    print("=" * 60)
    
    # Test 1: Content Hasher
    await test_content_hasher()
    
    # Test 2: Local/Mock Scraper Test
    await test_scraper_local()
    
    # Test 3: Live Browser Test
    print("\nRunning live browser test...")
    await test_scraper_with_browser()
    
    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETE!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())