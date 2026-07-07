import httpx
from ..config import APIFY_API_KEY, APIFY_BASE_URL, APIFY_ACTOR_ID

async def run_apify_scraper(category: str, city: str, country: str, max_results: int = 20):
    if not APIFY_API_KEY:
        raise ValueError("Apify API key not configured")

    input_data = {
        "category": category,
        "city": city,
        "country": country,
        "max_results": max_results,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{APIFY_BASE_URL}/acts/{APIFY_ACTOR_ID}/runs",
            params={"token": APIFY_API_KEY},
            json=input_data,
        )
        resp.raise_for_status()
        run_data = resp.json()
        return run_data.get("data", {}).get("id", "")

async def poll_apify_run(run_id: str):
    if not APIFY_API_KEY:
        raise ValueError("Apify API key not configured")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{APIFY_BASE_URL}/acts/{APIFY_ACTOR_ID}/runs/{run_id}",
            params={"token": APIFY_API_KEY},
        )
        resp.raise_for_status()
        return resp.json().get("data", {})

async def fetch_apify_results(run_id: str):
    if not APIFY_API_KEY:
        raise ValueError("Apify API key not configured")

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(
            f"{APIFY_BASE_URL}/acts/{APIFY_ACTOR_ID}/runs/{run_id}/dataset/items",
            params={"token": APIFY_API_KEY},
        )
        resp.raise_for_status()
        return resp.json()
