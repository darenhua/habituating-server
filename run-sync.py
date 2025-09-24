import asyncio
import aiohttp
import os
from typing import List, Dict, Any
import json
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
AUTH_TOKEN = os.getenv("AUTH_TOKEN")

if not AUTH_TOKEN:
    raise ValueError("AUTH_TOKEN environment variable is required")

HEADERS = {"Authorization": f"Bearer {AUTH_TOKEN}", "Content-Type": "application/json"}

MAX_RETRIES = 3
RETRY_DELAY = 1.0


async def make_request_with_retry(
    session: aiohttp.ClientSession, method: str, url: str, json_data: Dict = None
) -> Dict[str, Any]:
    """Make HTTP request with retry logic."""
    for attempt in range(MAX_RETRIES):
        try:
            async with session.request(
                method, url, headers=HEADERS, json=json_data
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    print(f"Request failed with status {response.status}: {error_text}")
                    if attempt == MAX_RETRIES - 1:
                        raise Exception(
                            f"Request failed after {MAX_RETRIES} attempts: {error_text}"
                        )
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {str(e)}")
            if attempt == MAX_RETRIES - 1:
                raise
            await asyncio.sleep(RETRY_DELAY * (attempt + 1))


async def step_1_create_sync_jobs(session: aiohttp.ClientSession) -> List[str]:
    """Step 1: Create sync course jobs and return job sync IDs."""
    print("Step 1: Creating sync course jobs...")

    url = f"{BASE_URL}/sync-course"
    response = await make_request_with_retry(session, "POST", url)

    job_syncs = response.get("job_syncs", [])
    job_sync_ids = [job_sync["id"] for job_sync in job_syncs]

    print(f"Created {len(job_sync_ids)} job syncs: {job_sync_ids}")
    return job_sync_ids


async def step_2_3_scrape_courses(
    session: aiohttp.ClientSession, job_sync_ids: List[str]
) -> None:
    """Steps 2-3: Scrape all courses in parallel."""
    print("Steps 2-3: Scraping courses in parallel...")

    async def scrape_single_course(job_sync_id: str):
        url = f"{BASE_URL}/sync-course/{job_sync_id}/scrape"
        response = await make_request_with_retry(session, "POST", url)
        print(
            f"Scraped job {job_sync_id}: {response.get('nodes_scraped', 0)} nodes, {response.get('assignment_pages_found', 0)} assignment pages"
        )
        return response

    tasks = [scrape_single_course(job_sync_id) for job_sync_id in job_sync_ids]
    await asyncio.gather(*tasks)
    print("All scraping completed!")


async def step_4_5_find_assignments(
    session: aiohttp.ClientSession, job_sync_ids: List[str]
) -> None:
    """Steps 4-5: Find assignments for all courses in parallel."""
    print("Steps 4-5: Finding assignments in parallel...")

    async def find_assignments_single_course(job_sync_id: str):
        url = f"{BASE_URL}/sync-course/{job_sync_id}/assignments"
        response = await make_request_with_retry(session, "POST", url)
        print(
            f"Found assignments for job {job_sync_id}: {response.get('assignments_found', 0)} found, {response.get('assignments_created', 0)} created"
        )
        return response

    tasks = [
        find_assignments_single_course(job_sync_id) for job_sync_id in job_sync_ids
    ]
    await asyncio.gather(*tasks)
    print("All assignment finding completed!")


async def step_6_7_find_due_dates(
    session: aiohttp.ClientSession, job_sync_ids: List[str]
) -> None:
    """Steps 6-7: Find due dates for all courses in parallel."""
    print("Steps 6-7: Finding due dates in parallel...")

    async def find_due_dates_single_course(job_sync_id: str):
        url = f"{BASE_URL}/sync-course/{job_sync_id}/due-dates"
        response = await make_request_with_retry(session, "POST", url)
        # print(
        #     f"Found due dates for job {job_sync_id}: {response.get('due_dates_found', 0)} found, {response.get('due_dates_created', 0)} created, {response.get('assignments_updated', 0)} assignments updated"
        # )
        return response

    tasks = [find_due_dates_single_course(job_sync_id) for job_sync_id in job_sync_ids]
    await asyncio.gather(*tasks)
    print("All due date finding completed!")


async def run_sync_pipeline():
    """Run the complete sync pipeline."""
    print(f"Starting sync pipeline with base URL: {BASE_URL}")

    async with aiohttp.ClientSession() as session:
        try:
            # Step 1: Create sync jobs
            job_sync_ids = await step_1_create_sync_jobs(session)

            if not job_sync_ids:
                print("No job syncs created. Exiting.")
                return

            # Steps 2-3: Scrape courses in parallel
            await step_2_3_scrape_courses(session, job_sync_ids)

            # Steps 4-5: Find assignments in parallel
            await step_4_5_find_assignments(session, job_sync_ids)

            # Steps 6-7: Find due dates in parallel
            await step_6_7_find_due_dates(session, job_sync_ids)

            print("🎉 Sync pipeline completed successfully!")

        except Exception as e:
            print(f"❌ Sync pipeline failed: {str(e)}")
            raise


def main():
    """Main entry point."""
    try:
        asyncio.run(run_sync_pipeline())
    except KeyboardInterrupt:
        print("\n🛑 Sync pipeline interrupted by user")
    except Exception as e:
        print(f"❌ Fatal error: {str(e)}")
        exit(1)


if __name__ == "__main__":
    main()
