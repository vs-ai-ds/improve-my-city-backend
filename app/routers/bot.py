# File: app\routers\bot.py
# Project: improve-my-city-backend
# Auto-added for reference

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.issue import Issue
import re

router = APIRouter(prefix="/bot", tags=["bot"])

@router.post("/ask")
def ask(payload: dict, db: Session = Depends(get_db)):
    q = (payload.get("q") or "").lower()
    m = re.search(r"(?:status.*#?)(\d+)", q)
    if m:
        iid = int(m.group(1))
        i = db.query(Issue).get(iid)
        if not i: return {"answer": f"I can’t find issue #{iid}."}
        status_str = i.status.value if hasattr(i.status, 'value') else str(i.status)
        return {"answer": f"Issue #{i.id} is {status_str.replace('_',' ')}."}
    return {"answer": "You can ask: 'What is the status of complaint #123?'"}
