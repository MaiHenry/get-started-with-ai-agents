import os
import httpx
from fastapi import HTTPException

CS_ENDPOINT = os.getenv("CONTENT_SAFETY_ENDPOINT", "").rstrip("/")
CS_KEY = os.getenv("CONTENT_SAFETY_KEY", "")

async def analyze_texts(texts: list[str]) -> list[dict]:
    if not CS_ENDPOINT or not CS_KEY:
        raise HTTPException(500, "Missing CONTENT_SAFETY_ENDPOINT or CONTENT_SAFETY_KEY")

    url = f"{CS_ENDPOINT}/contentsafety/text:analyze?api-version=2024-09-01"
    payload = {
        "items": [{"text": t} for t in texts],
        "categories": ["Hate", "Sexual", "Violence", "SelfHarm"],
        "outputType": "FourSeverity"
    }
    headers = {"Ocp-Apim-Subscription-Key": CS_KEY}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json=payload, headers=headers)
        r.raise_for_status()
        return r.json().get("items", [])
