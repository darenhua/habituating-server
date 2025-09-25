"""
Complete workflow test: Scraping -> Assignment Extraction -> Due Date Finding
Tests the entire idempotent pipeline with embedded HTML content
"""
import asyncio
import json
import tempfile
from pathlib import Path
from typing import Dict, List, Any
import uuid
from datetime import datetime

# Import our services
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.assignment_extractor import AssignmentExtractor
from services.due_date_finder import DueDateFinder

# Realistic HTML content that mimics actual course websites
REALISTIC_HTML_CONTENT = {
    "course_home": """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <title>COMS W4995: Advanced Topics in Distributed Systems</title>
        <meta charset="utf-8">
    </head>
    <body>
        <header>
            <h1>COMS W4995: Advanced Topics in Distributed Systems</h1>
            <p>Fall 2024 • Professor John Smith • MW 2:40-3:55 PM</p>
        </header>
        
        <nav>
            <ul>
                <li><a href="syllabus.html">Syllabus</a></li>
                <li><a href="assignments.html">Assignments</a></li>
                <li><a href="schedule.html">Schedule</a></li>
                <li><a href="resources.html">Resources</a></li>
            </ul>
        </nav>
        
        <main>
            <section id="announcements">
                <h2>Recent Announcements</h2>
                <div class="announcement">
                    <h3>Assignment 1 Posted</h3>
                    <p>The first programming assignment on Raft consensus has been posted. 
                    Please see the assignments page for details. <strong>Due October 15, 2024 at 11:59 PM.</strong></p>
                    <small>Posted: September 20, 2024</small>
                </div>
                <div class="announcement">
                    <h3>Course Project Guidelines Available</h3>
                    <p>Guidelines for the distributed systems project are now available. 
                    Projects will be due on <em>November 30, 2024 by 11:59 PM</em>.</p>
                    <small>Posted: September 25, 2024</small>
                </div>
            </section>
            
            <section id="overview">
                <h2>Course Overview</h2>
                <p>This course covers advanced topics in distributed systems including consensus, 
                replication, consistency models, and fault tolerance.</p>
            </section>
        </main>
    </body>
    </html>
    """,
    
    "assignments_detail": """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <title>Assignments - COMS W4995</title>
    </head>
    <body>
        <h1>Programming Assignments</h1>
        
        <div class="assignment-container">
            <div class="assignment" id="hw1">
                <div class="assignment-header">
                    <h2>Assignment 1: Raft Consensus Algorithm</h2>
                    <div class="assignment-meta">
                        <span class="posted-date">Posted: September 20, 2024</span>
                        <span class="due-date-highlight">⏰ Due: Tuesday, October 15, 2024 at 11:59 PM EST</span>
                    </div>
                </div>
                
                <div class="assignment-content">
                    <h3>Objective</h3>
                    <p>Implement a working Raft consensus algorithm in Go that can handle leader elections, 
                    log replication, and basic fault tolerance scenarios.</p>
                    
                    <h3>Requirements</h3>
                    <ul>
                        <li>Leader election with randomized timeouts</li>
                        <li>Log replication across multiple nodes</li>
                        <li>Proper handling of network partitions</li>
                        <li>Comprehensive test suite covering edge cases</li>
                    </ul>
                    
                    <h3>Deliverables</h3>
                    <p>Submit your implementation via Gradescope. Include:</p>
                    <ul>
                        <li>Complete source code</li>
                        <li>Test results and analysis</li>
                        <li>Brief design document (2-3 pages)</li>
                    </ul>
                    
                    <div class="deadline-reminder">
                        <strong>⚠️ IMPORTANT:</strong> This assignment is due on <u>October 15, 2024 at 11:59 PM EST</u>. 
                        Late submissions will be penalized 10% per day.
                    </div>
                </div>
            </div>
            
            <div class="assignment" id="project1">
                <div class="assignment-header">
                    <h2>Course Project: Distributed Key-Value Store</h2>
                    <div class="assignment-meta">
                        <span class="posted-date">Posted: October 1, 2024</span>
                        <span class="due-date-highlight">🗓️ Due: Saturday, November 30, 2024 at 11:59 PM EST</span>
                    </div>
                </div>
                
                <div class="assignment-content">
                    <h3>Project Description</h3>
                    <p>Design and implement a distributed key-value store that provides strong consistency 
                    guarantees while maintaining high availability and partition tolerance.</p>
                    
                    <h3>Technical Requirements</h3>
                    <ul>
                        <li>Multi-node architecture with replication (min 3 nodes)</li>
                        <li>Consensus-based consistency (using Raft or similar)</li>
                        <li>Client API for GET, PUT, DELETE operations</li>
                        <li>Failure detection and recovery mechanisms</li>
                        <li>Performance benchmarking suite</li>
                    </ul>
                    
                    <div class="project-timeline">
                        <h4>Important Dates</h4>
                        <ul>
                            <li>Project proposal due: October 20, 2024</li>
                            <li>Midterm check-in: November 15, 2024</li>
                            <li><strong>Final submission: November 30, 2024 at 11:59 PM</strong></li>
                            <li>Project presentations: December 5-7, 2024</li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
        
        <footer>
            <p>For questions about assignments, please post on the course forum or attend office hours.</p>
        </footer>
    </body>
    </html>
    """,
    
    "syllabus": """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <title>Syllabus - COMS W4995</title>
    </head>
    <body>
        <h1>Course Syllabus</h1>
        <h2>COMS W4995: Advanced Topics in Distributed Systems</h2>
        
        <section id="course-info">
            <h3>Course Information</h3>
            <ul>
                <li><strong>Instructor:</strong> Professor John Smith</li>
                <li><strong>Time:</strong> Mondays & Wednesdays, 2:40-3:55 PM</li>
                <li><strong>Location:</strong> Computer Science Building, Room 451</li>
                <li><strong>Credits:</strong> 3 points</li>
            </ul>
        </section>
        
        <section id="grading">
            <h3>Grading Breakdown</h3>
            <table>
                <tr><th>Component</th><th>Weight</th><th>Due Date</th></tr>
                <tr><td>Assignment 1 (Raft)</td><td>25%</td><td>October 15, 2024, 11:59 PM</td></tr>
                <tr><td>Midterm Exam</td><td>20%</td><td>October 25, 2024 (in class)</td></tr>
                <tr><td>Course Project</td><td>40%</td><td>November 30, 2024, 11:59 PM</td></tr>
                <tr><td>Final Exam</td><td>15%</td><td>TBD (Finals Week)</td></tr>
            </table>
        </section>
        
        <section id="assignments">
            <h3>Assignment Details</h3>
            
            <div class="assignment-summary">
                <h4>Assignment 1: Raft Consensus Implementation</h4>
                <p>Students will implement the Raft consensus algorithm, demonstrating understanding 
                of distributed consensus, leader election, and log replication.</p>
                <p><strong>Due:</strong> Tuesday, October 15, 2024 at 11:59 PM EST</p>
                <p><strong>Submission:</strong> Via Gradescope</p>
            </div>
            
            <div class="assignment-summary">
                <h4>Course Project: Distributed Storage System</h4>
                <p>A comprehensive project involving the design and implementation of a distributed 
                key-value store with strong consistency guarantees.</p>
                <p><strong>Final Due Date:</strong> Saturday, November 30, 2024 at 11:59 PM EST</p>
                <p><strong>Presentation:</strong> December 5-7, 2024</p>
            </div>
        </section>
        
        <section id="policies">
            <h3>Course Policies</h3>
            <h4>Late Assignment Policy</h4>
            <p>Assignments submitted late will incur a penalty of 10% per day late. 
            Assignments more than 5 days late will receive a grade of 0.</p>
            
            <h4>Final Project</h4>
            <p>The final project is due on <strong>November 30, 2024 at 11:59 PM</strong>. 
            No extensions will be granted for the final project without documented medical excuse.</p>
        </section>
    </body>
    </html>
    """
}

class MockNode:
    """Mock node for simulating scraped tree structure"""
    def __init__(self, url: str, title: str = "", html_path: str = ""):
        self.url = url
        self.title = title
        self.html_path = html_path
        self.content_hash = f"hash_{uuid.uuid4().hex[:8]}"
        self.content_changed = True
        self.children = []

class TestCompleteWorkflow:
    """Test the complete workflow from scraping to due date extraction"""
    
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
        self.job_sync_id = f"workflow_test_{uuid.uuid4().hex[:8]}"
        
    def create_test_files(self) -> Dict[str, str]:
        """Create realistic test HTML files"""
        file_paths = {}
        
        for filename, content in REALISTIC_HTML_CONTENT.items():
            file_path = Path(self.temp_dir) / f"{filename}.html"
            file_path.write_text(content, encoding='utf-8')
            file_paths[filename] = str(file_path)
        
        return file_paths
    
    def create_mock_scraped_tree(self, file_paths: Dict[str, str]) -> Dict[str, Any]:
        """Create mock scraped tree structure"""
        return {
            "url": "https://systems.cs.columbia.edu/course/",
            "title": "COMS W4995: Advanced Topics in Distributed Systems",
            "html_path": file_paths["course_home"],
            "content_hash": "hash_home_123",
            "content_changed": True,
            "previous_hash": None,
            "last_scraped": datetime.now().isoformat(),
            "children": [
                {
                    "url": "https://systems.cs.columbia.edu/course/assignments",
                    "title": "Assignments - COMS W4995",
                    "html_path": file_paths["assignments_detail"],
                    "content_hash": "hash_assignments_456",
                    "content_changed": True,
                    "previous_hash": None,
                    "last_scraped": datetime.now().isoformat(),
                    "children": []
                },
                {
                    "url": "https://systems.cs.columbia.edu/course/syllabus",
                    "title": "Syllabus - COMS W4995",
                    "html_path": file_paths["syllabus"],
                    "content_hash": "hash_syllabus_789",
                    "content_changed": True,
                    "previous_hash": None,
                    "last_scraped": datetime.now().isoformat(),
                    "children": []
                }
            ]
        }
    
    async def run_assignment_extraction_test(self, scraped_tree: Dict[str, Any]) -> List[Dict]:
        """Test assignment extraction phase"""
        
        print("📝 PHASE 1: Assignment Extraction")
        print("-" * 40)
        
        # Mock the assignment extractor methods for testing
        extractor = AssignmentExtractor(supabase_client=None)
        
        # Override HTML loading
        async def mock_load_html(html_path: str) -> str:
            try:
                return Path(html_path).read_text(encoding='utf-8')
            except Exception as e:
                print(f"Error loading {html_path}: {e}")
                return ""
        
        extractor.load_html_from_storage = mock_load_html
        
        # Mock find_existing_assignment to return None (all new assignments)
        async def mock_find_existing(title: str, description: str):
            return None
        extractor.find_existing_assignment = mock_find_existing
        
        # Mock create_new_assignment to just print what would be created
        created_assignments = []
        async def mock_create_assignment(assignment, html_path, job_sync_id):
            assignment_data = {
                "id": f"assignment_{uuid.uuid4().hex[:8]}",
                "title": assignment.title,
                "description": assignment.description,
                "source_page_paths": [html_path],
                "content_hash": assignment.content_hash,
                "source_url": assignment.source_url
            }
            created_assignments.append(assignment_data)
            print(f"   📌 Would create assignment: {assignment.title}")
        
        extractor.create_new_assignment = mock_create_assignment
        
        # Run assignment extraction
        assignments = await extractor.extract_all_assignments(
            scraped_tree, 
            self.job_sync_id
        )
        
        print(f"   ✅ Extracted {len(assignments)} assignments from content")
        
        # Convert to format expected by due date finder
        formatted_assignments = []
        for assignment in assignments:
            # Find the created assignment data
            matching_created = next((ca for ca in created_assignments if ca["title"] == assignment.title), None)
            if matching_created:
                formatted_assignments.append(matching_created)
        
        return formatted_assignments
    
    async def run_due_date_extraction_test(self, assignments: List[Dict]) -> List[Any]:
        """Test due date extraction phase"""
        
        print(f"\n📅 PHASE 2: Due Date Extraction")
        print("-" * 40)
        
        due_date_finder = DueDateFinder(supabase_client=None)
        
        # Override HTML loading
        async def mock_load_html(html_path: str) -> str:
            try:
                return Path(html_path).read_text(encoding='utf-8')
            except Exception as e:
                print(f"Error loading {html_path}: {e}")
                return ""
        
        due_date_finder.load_html_from_storage = mock_load_html
        
        # Run due date extraction
        due_dates = await due_date_finder.find_due_dates(
            scraped_tree={},  # Not used in new implementation
            assignments=assignments,
            job_sync_id=self.job_sync_id
        )
        
        print(f"   ✅ Processed {len(assignments)} assignments for due dates")
        
        return due_dates
    
    def validate_results(self, assignments: List[Dict], due_dates: List[Any]) -> Dict[str, Any]:
        """Validate the complete workflow results"""
        
        print(f"\n🔍 PHASE 3: Results Validation")
        print("-" * 40)
        
        # Expected results
        expected_assignments = {
            "raft": {"title_contains": "Raft", "date_expected": "October 15, 2024"},
            "project": {"title_contains": "Key-Value", "date_expected": "November 30, 2024"}
        }
        
        validation_results = {
            "assignment_extraction": {
                "total_expected": len(expected_assignments),
                "total_found": len(assignments),
                "matches": []
            },
            "due_date_extraction": {
                "total_assignments": len(assignments),
                "dates_found": len([dd for dd in due_dates if dd.date]),
                "dates_missing": len([dd for dd in due_dates if not dd.date]),
                "matches": []
            }
        }
        
        # Validate assignment extraction
        print("   📊 Assignment Extraction Validation:")
        for assignment in assignments:
            found_match = False
            for expected_key, expected_data in expected_assignments.items():
                if expected_data["title_contains"].lower() in assignment["title"].lower():
                    validation_results["assignment_extraction"]["matches"].append({
                        "assignment_id": assignment["id"],
                        "title": assignment["title"],
                        "expected_key": expected_key,
                        "match": True
                    })
                    print(f"     ✅ Found expected assignment: {assignment['title']}")
                    found_match = True
                    break
            
            if not found_match:
                print(f"     ❓ Unexpected assignment: {assignment['title']}")
        
        # Validate due date extraction
        print("   📅 Due Date Extraction Validation:")
        for due_date in due_dates:
            if due_date.date:
                found_match = False
                for expected_key, expected_data in expected_assignments.items():
                    if expected_data["title_contains"].lower() in due_date.assignment_title.lower():
                        expected_date = expected_data["date_expected"]
                        date_match = expected_date.replace(" ", "").lower() in due_date.date.replace(" ", "").lower()
                        
                        validation_results["due_date_extraction"]["matches"].append({
                            "assignment_title": due_date.assignment_title,
                            "found_date": due_date.date,
                            "expected_date": expected_date,
                            "match": date_match,
                            "confidence": due_date.confidence
                        })
                        
                        if date_match:
                            print(f"     ✅ Correct date for {due_date.assignment_title}: {due_date.date}")
                        else:
                            print(f"     ❌ Wrong date for {due_date.assignment_title}: got {due_date.date}, expected {expected_date}")
                        
                        found_match = True
                        break
                
                if not found_match:
                    print(f"     ❓ Unexpected due date: {due_date.assignment_title} - {due_date.date}")
            else:
                print(f"     ❌ No date found for: {due_date.assignment_title}")
                print(f"         Reasoning: {due_date.reasoning}")
        
        return validation_results
    
    async def run_complete_test(self):
        """Run the complete workflow test"""
        
        print("🚀 Complete Workflow Test: Scraping → Assignment Extraction → Due Date Finding")
        print("=" * 80)
        
        # Setup
        file_paths = self.create_test_files()
        scraped_tree = self.create_mock_scraped_tree(file_paths)
        
        print(f"📁 Test setup completed:")
        print(f"   Temporary directory: {self.temp_dir}")
        print(f"   Created {len(file_paths)} HTML files")
        print(f"   Job Sync ID: {self.job_sync_id}")
        
        try:
            # Phase 1: Assignment Extraction
            assignments = await self.run_assignment_extraction_test(scraped_tree)
            
            # Phase 2: Due Date Extraction  
            due_dates = await self.run_due_date_extraction_test(assignments)
            
            # Phase 3: Validation
            validation_results = self.validate_results(assignments, due_dates)
            
            # Summary
            print(f"\n🎯 WORKFLOW TEST SUMMARY")
            print("=" * 50)
            
            assignment_success = len(validation_results["assignment_extraction"]["matches"])
            assignment_expected = validation_results["assignment_extraction"]["total_expected"]
            
            date_success = len([m for m in validation_results["due_date_extraction"]["matches"] if m["match"]])
            date_total = len(assignments)
            
            print(f"📝 Assignment Extraction: {assignment_success}/{assignment_expected} expected assignments found")
            print(f"📅 Due Date Extraction: {date_success}/{date_total} correct dates found")
            
            overall_success = (assignment_success == assignment_expected and date_success >= assignment_expected)
            
            if overall_success:
                print(f"🎉 WORKFLOW TEST PASSED! All components working correctly.")
            else:
                print(f"⚠️  WORKFLOW TEST PARTIAL SUCCESS - some issues detected.")
            
            # Export detailed results
            export_data = {
                "test_metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "job_sync_id": self.job_sync_id,
                    "temp_directory": self.temp_dir
                },
                "scraped_tree": scraped_tree,
                "extracted_assignments": assignments,
                "due_dates": [
                    {
                        "assignment_id": dd.assignment_id,
                        "assignment_title": dd.assignment_title,
                        "date": dd.date,
                        "confidence": dd.confidence,
                        "reasoning": dd.reasoning,
                        "date_certain": dd.date_certain,
                        "time_certain": dd.time_certain
                    } for dd in due_dates
                ],
                "validation_results": validation_results,
                "test_summary": {
                    "assignment_success_rate": assignment_success / assignment_expected if assignment_expected > 0 else 0,
                    "due_date_success_rate": date_success / date_total if date_total > 0 else 0,
                    "overall_success": overall_success
                }
            }
            
            results_file = "test_complete_workflow_results.json"
            with open(results_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            print(f"📄 Complete results exported to: {results_file}")
            
            return overall_success
            
        except Exception as e:
            print(f"💥 Workflow test failed: {e}")
            import traceback
            traceback.print_exc()
            return False

async def main():
    """Main test execution"""
    
    test_runner = TestCompleteWorkflow()
    
    try:
        success = await test_runner.run_complete_test()
        
        if success:
            print("\n🎊 Complete workflow test PASSED!")
            return 0
        else:
            print("\n❌ Complete workflow test had issues.")
            return 1
            
    except Exception as e:
        print(f"\n💥 Test runner failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)