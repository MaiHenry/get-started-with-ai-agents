from fastapi import APIRouter, HTTPException, Query
import os, re, httpx
from typing import List, Dict, Any

router = APIRouter(prefix="/fb", tags=["facebook"])
FB_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN", "")

def _extract_post_id(url_or_id: str) -> str:
    if url_or_id.isdigit(): return url_or_id
    m = (re.search(r"/posts/(\d+)", url_or_id)
         or re.search(r"/photos/(\d+)", url_or_id)
         or re.search(r"/videos/(\d+)", url_or_id)
         or re.search(r"(\d+)(?:\?.*)?$", url_or_id))
    if m:
        for g in m.groups():
            if g: return g
    raise HTTPException(400, "Could not parse post_id from URL.")

async def _fetch_all_comments(post_id: str, max_pages: int = 1) -> List[Dict[str, Any]]:
    if not FB_TOKEN:
        raise HTTPException(500, "Missing FB_PAGE_ACCESS_TOKEN env var.")
    url = f"https://graph.facebook.com/v23.0/{post_id}/comments"
    params = {
        "access_token": FB_TOKEN,
        "filter": "stream",
        "limit": 100,
        "fields": "id,message,from,created_time,is_hidden"
    }
    out, pages = [], 0
    async with httpx.AsyncClient(timeout=20) as client:
        while True:
            r = await client.get(url, params=params)
            if r.status_code in (400,403): raise HTTPException(r.status_code, r.text)
            r.raise_for_status()
            data = r.json()
            out += [c for c in data.get("data", []) if c.get("message")]
            next_url = data.get("paging", {}).get("next")
            pages += 1
            if not next_url or pages >= max_pages: break
            url, params = next_url, {}
    return out

@router.get("/comments")
async def list_comments(postUrl: str = Query(...), maxPages: int = 1):
    post_id = _extract_post_id(postUrl)
    comments = await _fetch_all_comments(post_id, max_pages=maxPages)
    return {"post_id": post_id, "count": len(comments), "results": comments}
