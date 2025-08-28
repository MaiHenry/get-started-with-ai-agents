import os, re
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Query
import httpx

router = APIRouter(prefix="/fb", tags=["facebook"])

FB_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN", "")
CS_ENDPOINT = os.getenv("CONTENT_SAFETY_ENDPOINT", "").rstrip("/")
CS_KEY = os.getenv("CONTENT_SAFETY_KEY", "")

def _extract_post_id(url_or_id: str) -> str:
    # Accept numeric ID or common post URL shapes
    if url_or_id.isdigit():
        return url_or_id
    m = (re.search(r"/posts/(\d+)", url_or_id)
         or re.search(r"/photos/(\d+)", url_or_id)
         or re.search(r"/videos/(\d+)", url_or_id)
         or re.search(r"(\d+)(?:\?.*)?$", url_or_id))
    if m:
        for g in m.groups():
            if g: return g
    raise HTTPException(400, "Could not parse post_id from URL. Paste the numeric post ID or a post URL.")

async def _fetch_all_comments(post_id: str) -> List[Dict[str, Any]]:
    if not FB_TOKEN:
        raise HTTPException(500, "Missing FB_PAGE_ACCESS_TOKEN env var.")
    url = f"https://graph.facebook.com/v21.0/{post_id}/comments"
    params = {
        "access_token": FB_TOKEN,
        "filter": "stream",
        "limit": 100,
        "fields": "id,message,from,created_time,parent,like_count,is_hidden"
    }
    out: List[Dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            r = await client.get(url, params=params)
            if r.status_code == 400 and "Unsupported get request" in r.text:
                raise HTTPException(400, "Facebook says this post is not accessible with your token/permissions.")
            r.raise_for_status()
            data = r.json()
            out.extend([c for c in data.get("data", []) if c.get("message")])
            next_url = data.get("paging", {}).get("next")
            if not next_url:
                break
            url, params = next_url, {}  # 'next' is a full URL
    return out

async def _score_texts(texts: List[str]) -> List[Dict[str, Any]]:
    if not (CS_ENDPOINT and CS_KEY):
        raise HTTPException(500, "Missing CONTENT_SAFETY_ENDPOINT / CONTENT_SAFETY_KEY env vars.")
    api = f"{CS_ENDPOINT}/contentsafety/text:analyze?api-version=2024-09-01"
    payload = {
        "items": [{"text": t} for t in texts],
        "categories": ["Hate", "Sexual", "Violence", "SelfHarm"],
        "outputType": "FourSeverity"  # 0,2,4,6
    }
    headers = {"Ocp-Apim-Subscription-Key": CS_KEY}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(api, json=payload, headers=headers)
        r.raise_for_status()
        return r.json().get("items", [])

@router.get("/analyze")
async def analyze(
    postUrl: str = Query(..., description="Facebook post URL or numeric post_id")
):
    """
    Paste a Facebook post URL; returns all comments with Content Safety scores
    so you can review them manually. No actions are suggested.
    """
    post_id = _extract_post_id(postUrl)
    comments = await _fetch_all_comments(post_id)
    scores = await _score_texts([c["message"] for c in comments])

    results = []
    for c, s in zip(comments, scores):
        results.append({
            "id": c["id"],
            "author": c.get("from", {}),
            "created_time": c.get("created_time"),
            "message": c["message"],
            "is_hidden": c.get("is_hidden"),
            "categories": s.get("categoriesAnalysis", [])
        })

    return {"post_id": post_id, "count": len(results), "results": results}
