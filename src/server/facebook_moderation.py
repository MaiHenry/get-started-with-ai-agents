from fastapi import APIRouter, Body
from server.content_safety import analyze_texts

router = APIRouter(prefix="/fb", tags=["facebook"])

@router.post("/moderate-test")
async def moderate_test(comments: list[str] = Body(..., embed=True)):
    scores = await analyze_texts(comments)
    out = []
    for text, s in zip(comments, scores):
        cats = s.get("categoriesAnalysis", [])
        max_sev = max((c.get("severity", 0) for c in cats), default=0)
        action = "ok"
        if max_sev >= 6: action = "delete"
        elif max_sev >= 4: action = "review"
        out.append({
            "text": text,
            "max_severity": max_sev,
            "categories": cats,
            "suggested_action": action
        })
    return {"count": len(out), "items": out}
