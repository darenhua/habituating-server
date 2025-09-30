"""
Temporal worker with enhanced error handling and debugging output.
This version will show exactly where and why the worker fails to start.
"""

import asyncio
import os
import sys
import traceback
from pathlib import Path

# Add the project root to the Python path so we can import temporal modules (parent of temporal directory)
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from temporalio.client import Client
from temporalio.worker import Worker

async def main() -> None:
    """Start the Temporal worker with detailed error handling."""
    print("🚀 Starting Temporal Worker (Debug Mode)")
    
    # Get configuration from environment
    temporal_host = os.getenv("TEMPORAL_HOST", "localhost:7233")
    temporal_namespace = os.getenv("TEMPORAL_NAMESPACE", "default")
    
    print(f"Configuration:")
    print(f"  TEMPORAL_HOST: {temporal_host}")
    print(f"  TEMPORAL_NAMESPACE: {temporal_namespace}")
    print(f"  SUPABASE_URL: {'SET' if os.getenv('SUPABASE_URL') else 'MISSING'}")
    print(f"  SUPABASE_ANON_KEY: {'SET' if os.getenv('SUPABASE_ANON_KEY') else 'MISSING'}")
    
    # Step 1: Test imports
    print(f"\n📦 Testing imports...")
    try:
        from temporal.shared import COURSE_SYNC_TASK_QUEUE_NAME
        print(f"  ✅ temporal.shared imported")
        
        from temporal.courses.workflows import CourseSyncWorkflow
        print(f"  ✅ temporal.courses.workflows imported")
        
        from temporal.courses.activities import CourseSyncActivities
        print(f"  ✅ temporal.courses.activities imported")
        
    except Exception as e:
        print(f"  ❌ Import failed: {e}")
        traceback.print_exc()
        return
    
    # Step 2: Test Temporal connection
    print(f"\n🌐 Testing Temporal connection...")
    try:
        print(f"  Connecting to {temporal_host}, namespace: {temporal_namespace}")
        client: Client = await Client.connect(
            temporal_host, 
            namespace=temporal_namespace
        )
        print(f"  ✅ Connected to Temporal server")
    except Exception as e:
        print(f"  ❌ Temporal connection failed: {e}")
        traceback.print_exc()
        return
    
    # Step 3: Test activities initialization  
    print(f"\n🎯 Testing activities initialization...")
    try:
        activities = CourseSyncActivities()
        print(f"  ✅ Activities initialized successfully")
    except Exception as e:
        print(f"  ❌ Activities initialization failed: {e}")
        traceback.print_exc()
        print(f"\n💡 This is likely due to missing environment variables.")
        print(f"💡 Make sure SUPABASE_URL and SUPABASE_ANON_KEY are set.")
        return
    
    # Step 4: Create worker
    print(f"\n⚙️  Creating worker...")
    try:
        print(f"  Task queue: {COURSE_SYNC_TASK_QUEUE_NAME}")
        
        worker: Worker = Worker(
            client,
            task_queue=COURSE_SYNC_TASK_QUEUE_NAME,
            workflows=[CourseSyncWorkflow],
            activities=[
                activities.create_sync_jobs,
                activities.scrape_course,
                activities.find_assignments,
                activities.find_due_dates,
            ],
        )
        print(f"  ✅ Worker created successfully")
        
    except Exception as e:
        print(f"  ❌ Worker creation failed: {e}")
        traceback.print_exc()
        return
    
    # Step 5: Start worker
    print(f"\n🚀 Starting worker...")
    print(f"Press Ctrl+C to stop the worker\n")
    
    try:
        await worker.run()
    except KeyboardInterrupt:
        print(f"\n🛑 Worker stopped by user")
    except Exception as e:
        print(f"❌ Worker failed during execution: {e}")
        traceback.print_exc()
        raise

if __name__ == "__main__":
    asyncio.run(main())