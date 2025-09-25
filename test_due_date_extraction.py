"""
Test script specifically for the new due date extraction functionality
Tests the complete workflow with mock HTML content containing due dates
"""
import asyncio
import json
import tempfile
from pathlib import Path
from typing import Dict, List, Any
import uuid
from datetime import datetime

# Import our new services
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.due_date_finder import DueDateFinder

# Mock HTML content with embedded due dates in various formats
MOCK_HTML_PAGES = {
    "syllabus": """
    <!DOCTYPE html>
    <html>
    <head>
        <title>CS 4995 - Distributed Systems Syllabus</title>
    </head>
    <body>
        <h1>Distributed Systems Course Syllabus</h1>
        <h2>Course Assignments</h2>
        <div class="assignments-section">
            <div class="assignment-item">
                <h3>Homework 1: Consensus Algorithms</h3>
                <p>Students will implement the Raft consensus algorithm in Go.</p>
                <p class="due-info"><strong>Due Date:</strong> October 15, 2024 at 11:59 PM EST</p>
                <p>Weight: 20% of final grade</p>
            </div>
            
            <div class="assignment-item">
                <h3>Project 1: Distributed Key-Value Store</h3>
                <p>Build a fault-tolerant distributed key-value storage system with replication.</p>
                <p class="deadline-info"><em>Deadline: November 30, 2024 by 11:59 PM EST</em></p>
                <p>Weight: 35% of final grade</p>
            </div>
            
            <div class="assignment-item">
                <h3>Final Research Project</h3>
                <p>Original research project on distributed systems topics.</p>
                <p class="submit-info">Submit final report by <strong>December 20, 2024 at 11:59 PM EST</strong></p>
                <p>Weight: 30% of final grade</p>
            </div>
        </div>
    </body>
    </html>
    """,
    
    "assignments_page": """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Programming Assignments - CS 4995</title>
    </head>
    <body>
        <h1>Programming Assignments</h1>
        
        <article class="assignment">
            <header>
                <h2>Assignment 1: Raft Consensus Implementation</h2>
                <div class="metadata">
                    <span class="posted">Posted: September 20, 2024</span>
                    <span class="due">Due: Tuesday, October 15, 2024 at 11:59 PM</span>
                </div>
            </header>
            
            <section class="description">
                <p>In this assignment, you will implement the Raft consensus algorithm in Go.</p>
                <h3>Requirements:</h3>
                <ul>
                    <li>Leader election mechanism</li>
                    <li>Log replication with proper ordering</li>
                    <li>Safety properties enforcement</li>
                    <li>Comprehensive test suite</li>
                </ul>
            </section>
            
            <section class="submission">
                <p><strong>Submission:</strong> Submit your code via Gradescope by the deadline.</p>
                <p><strong>Late Policy:</strong> 10% penalty per day late.</p>
            </section>
        </article>

        <article class="assignment">
            <header>
                <h2>Midterm Project: Distributed Storage System</h2>
                <div class="metadata">
                    <span class="posted">Posted: October 20, 2024</span>
                    <span class="due-date">📅 Due: Saturday, November 30, 2024 at 11:59 PM EST</span>
                </div>
            </header>
            
            <section class="description">
                <p>Build a comprehensive distributed key-value storage system.</p>
                <h3>Core Features:</h3>
                <ul>
                    <li>Multi-node replication</li>
                    <li>Consistency guarantees (strong or eventual)</li>
                    <li>Partition tolerance and failure recovery</li>
                    <li>Performance benchmarking</li>
                </ul>
            </section>
        </article>
    </body>
    </html>
    """,
    
    "schedule": """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Course Schedule - CS 4995</title>
    </head>
    <body>
        <h1>Course Schedule - Fall 2024</h1>
        
        <div class="month-section">
            <h2>October 2024</h2>
            <table class="schedule-table">
                <tr>
                    <th>Date</th>
                    <th>Topic</th>
                    <th>Assignments</th>
                </tr>
                <tr>
                    <td>October 1</td>
                    <td>Consensus Algorithms</td>
                    <td>-</td>
                </tr>
                <tr class="assignment-due">
                    <td>October 15</td>
                    <td>Midterm Review</td>
                    <td><strong>HW1 (Raft Implementation) DUE at 11:59 PM</strong></td>
                </tr>
                <tr>
                    <td>October 22</td>
                    <td>Distributed Storage</td>
                    <td>Project 1 assigned</td>
                </tr>
            </table>
        </div>
        
        <div class="month-section">
            <h2>November 2024</h2>
            <table class="schedule-table">
                <tr>
                    <th>Date</th>
                    <th>Topic</th>
                    <th>Assignments</th>
                </tr>
                <tr>
                    <td>November 5</td>
                    <td>Replication Strategies</td>
                    <td>-</td>
                </tr>
                <tr>
                    <td>November 19</td>
                    <td>CAP Theorem</td>
                    <td>-</td>
                </tr>
                <tr class="assignment-due">
                    <td>November 30</td>
                    <td>Project Presentations</td>
                    <td><em>Project 1: Distributed KV Store due 11:59 PM</em></td>
                </tr>
            </table>
        </div>

        <div class="month-section">
            <h2>December 2024</h2>
            <table class="schedule-table">
                <tr>
                    <th>Date</th>
                    <th>Topic</th>
                    <th>Assignments</th>
                </tr>
                <tr>
                    <td>December 10</td>
                    <td>Final Project Presentations</td>
                    <td>-</td>
                </tr>
                <tr class="final-due">
                    <td>December 20</td>
                    <td>Finals Week</td>
                    <td><strong>Final Research Project Report Due 11:59 PM</strong></td>
                </tr>
            </table>
        </div>
    </body>
    </html>
    """
}

class TestDueDateExtraction:
    """Test suite for due date extraction functionality"""
    
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
        self.job_sync_id = f"test_sync_{uuid.uuid4().hex[:8]}"
        
    def create_html_files(self) -> Dict[str, str]:
        """Create temporary HTML files and return their paths"""
        html_paths = {}
        
        for page_name, html_content in MOCK_HTML_PAGES.items():
            file_path = Path(self.temp_dir) / f"{page_name}.html"
            file_path.write_text(html_content, encoding='utf-8')
            html_paths[page_name] = str(file_path)
        
        return html_paths
    
    def create_mock_assignments(self, html_paths: Dict[str, str]) -> List[Dict]:
        """Create mock assignments with source_page_paths"""
        
        assignments = [
            {
                "id": f"hw1_{uuid.uuid4().hex[:8]}",
                "title": "Homework 1: Consensus Algorithms",
                "description": "Implement the Raft consensus algorithm in Go with leader election, log replication, and safety properties.",
                "source_page_paths": [
                    html_paths["syllabus"],
                    html_paths["assignments_page"],
                    html_paths["schedule"]
                ]
            },
            {
                "id": f"project1_{uuid.uuid4().hex[:8]}",
                "title": "Project 1: Distributed Key-Value Store",
                "description": "Build a fault-tolerant distributed key-value storage system with replication and consistency guarantees.",
                "source_page_paths": [
                    html_paths["syllabus"],
                    html_paths["assignments_page"],
                    html_paths["schedule"]
                ]
            },
            {
                "id": f"final_{uuid.uuid4().hex[:8]}",
                "title": "Final Research Project",
                "description": "Original research project on distributed systems topics with comprehensive analysis.",
                "source_page_paths": [
                    html_paths["syllabus"],
                    html_paths["schedule"]
                ]
            }
        ]
        
        return assignments
    
    async def run_due_date_test(self):
        """Run comprehensive due date extraction test"""
        
        print("🧪 Testing Due Date Extraction System")
        print("=" * 60)
        
        # Setup
        html_paths = self.create_html_files()
        assignments = self.create_mock_assignments(html_paths)
        
        print(f"📁 Created temporary files in: {self.temp_dir}")
        print(f"📝 Created {len(assignments)} test assignments")
        print(f"📄 Created {len(html_paths)} HTML pages")
        
        # Initialize due date finder
        due_date_finder = DueDateFinder(supabase_client=None)
        
        # Override the HTML loading method to use local files
        async def mock_load_html(html_path: str) -> str:
            try:
                return Path(html_path).read_text(encoding='utf-8')
            except Exception as e:
                print(f"⚠️  Error loading {html_path}: {e}")
                return ""
        
        due_date_finder.load_html_from_storage = mock_load_html
        
        print(f"\n🔍 Starting due date extraction...")
        print(f"   Job Sync ID: {self.job_sync_id}")
        
        # Run due date extraction
        due_dates = await due_date_finder.find_due_dates(
            scraped_tree={},  # Not used in new implementation
            assignments=assignments,
            job_sync_id=self.job_sync_id
        )
        
        # Analyze results
        print(f"\n📊 Extraction Results:")
        print(f"   Total assignments: {len(assignments)}")
        print(f"   Due dates found: {len([dd for dd in due_dates if dd.date])}")
        print(f"   No dates found: {len([dd for dd in due_dates if not dd.date])}")
        
        # Expected results for validation
        expected_results = {
            "Homework 1": {
                "date_contains": "October 15, 2024",
                "time_contains": "11:59 PM"
            },
            "Project 1": {
                "date_contains": "November 30, 2024", 
                "time_contains": "11:59 PM"
            },
            "Final": {
                "date_contains": "December 20, 2024",
                "time_contains": "11:59 PM"
            }
        }
        
        print(f"\n📋 Detailed Results:")
        print("-" * 60)
        
        validation_results = []
        
        for due_date in due_dates:
            assignment_name = due_date.assignment_title
            print(f"\n📌 {assignment_name}")
            print(f"   ID: {due_date.assignment_id}")
            
            if due_date.date:
                print(f"   📅 Date Found: {due_date.date}")
                print(f"   ✔️  Date Certain: {due_date.date_certain}")
                print(f"   ⏰ Time Certain: {due_date.time_certain}")
                print(f"   🎯 Confidence: {due_date.confidence:.2f}")
                print(f"   📝 Reasoning: {due_date.reasoning}")
                print(f"   🔗 Source Count: {len(due_date.source_urls)}")
                
                # Validation
                found_expected = False
                for expected_key, expected_data in expected_results.items():
                    if expected_key.lower() in assignment_name.lower():
                        expected_date = expected_data["date_contains"]
                        expected_time = expected_data["time_contains"]
                        
                        date_match = expected_date.replace(" ", "").lower() in due_date.date.replace(" ", "").lower()
                        time_match = expected_time.lower() in due_date.date.lower()
                        
                        if date_match:
                            print(f"   ✅ Date validation: PASSED (found expected date)")
                            validation_results.append({"assignment": assignment_name, "date_valid": True, "time_valid": time_match})
                        else:
                            print(f"   ❌ Date validation: FAILED (expected: {expected_date})")
                            validation_results.append({"assignment": assignment_name, "date_valid": False, "time_valid": False})
                        
                        found_expected = True
                        break
                
                if not found_expected:
                    print(f"   ⚠️  No validation criteria found for this assignment")
                    validation_results.append({"assignment": assignment_name, "date_valid": None, "time_valid": None})
                
            else:
                print(f"   ❌ No Due Date Found")
                print(f"   📝 Reasoning: {due_date.reasoning}")
                validation_results.append({"assignment": assignment_name, "date_valid": False, "time_valid": False})
        
        # Overall validation summary
        print(f"\n🎯 Validation Summary:")
        print("=" * 60)
        
        total_assignments = len(validation_results)
        successful_dates = len([r for r in validation_results if r["date_valid"] == True])
        successful_times = len([r for r in validation_results if r["time_valid"] == True])
        
        print(f"   📊 Date Extraction Success: {successful_dates}/{total_assignments} ({successful_dates/total_assignments*100:.1f}%)")
        print(f"   ⏰ Time Extraction Success: {successful_times}/{total_assignments} ({successful_times/total_assignments*100:.1f}%)")
        
        if successful_dates == total_assignments:
            print(f"   🎉 ALL DATE EXTRACTIONS PASSED!")
        else:
            print(f"   ⚠️  {total_assignments - successful_dates} date extractions failed")
        
        # Export detailed results
        export_data = {
            "test_metadata": {
                "timestamp": datetime.now().isoformat(),
                "job_sync_id": self.job_sync_id,
                "temp_dir": self.temp_dir,
                "total_assignments": total_assignments
            },
            "test_assignments": assignments,
            "extraction_results": [
                {
                    "assignment_id": dd.assignment_id,
                    "assignment_title": dd.assignment_title,
                    "date_found": dd.date,
                    "date_certain": dd.date_certain,
                    "time_certain": dd.time_certain,
                    "confidence": dd.confidence,
                    "source_urls": dd.source_urls,
                    "reasoning": dd.reasoning
                }
                for dd in due_dates
            ],
            "validation_summary": {
                "successful_dates": successful_dates,
                "successful_times": successful_times,
                "total_assignments": total_assignments,
                "date_success_rate": successful_dates/total_assignments,
                "time_success_rate": successful_times/total_assignments
            },
            "validation_details": validation_results
        }
        
        results_file = "test_due_date_results.json"
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 Detailed results exported to: {results_file}")
        
        # Return success status
        return successful_dates == total_assignments

async def main():
    """Main test execution"""
    
    print("🚀 Starting Due Date Extraction Test Suite")
    print("This test validates that due dates embedded in HTML are correctly extracted")
    print()
    
    test_runner = TestDueDateExtraction()
    
    try:
        success = await test_runner.run_due_date_test()
        
        if success:
            print("\n🎊 All tests PASSED! Due date extraction is working correctly.")
            return 0
        else:
            print("\n❌ Some tests FAILED. Check the results above for details.")
            return 1
            
    except Exception as e:
        print(f"\n💥 Test suite failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)