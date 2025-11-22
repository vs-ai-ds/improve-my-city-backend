# File: app\routers\bot.py
# Project: improve-my-city-backend

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import get_optional_user
from app.models.issue import Issue, IssueStatus
from app.models.user import User
from app.models.app_settings import AppSettings
import re
from typing import Optional
from difflib import get_close_matches

router = APIRouter(prefix="/bot", tags=["bot"])

FAQ_ENTRIES = [
    {
        "id": "how_report",
        "patterns": ["how to report", "report an issue", "submit a complaint", "how do i report", "report issue"],
        "answer": "You can report an issue by clicking the 'Report an issue' button on the dashboard. You'll select a category, location on the map, and optionally upload photos. You can report anonymously if that's enabled, or login for better tracking."
    },
    {
        "id": "statuses",
        "patterns": ["what are the statuses", "pending vs in progress", "what does resolved mean", "status meaning", "what do statuses mean"],
        "answer": "Issues can be:\n• Pending: Waiting to be picked up by staff\n• In Progress: Someone is actively working on it\n• Resolved: The issue has been fixed"
    },
    {
        "id": "anonymous",
        "patterns": ["anonymous reporting", "report without login", "can i report anonymously"],
        "answer": "Anonymous reporting depends on your city's settings. Check the dashboard - if you see a 'Report an issue' button without logging in, it's enabled."
    },
    {
        "id": "login_help",
        "patterns": ["how to login", "sign in", "how do i login", "login help"],
        "answer": "To login, click the 'Sign in' button at the top right. If you haven't verified your email yet, you'll receive a verification link/code by email."
    },
    {
        "id": "verification",
        "patterns": ["verification", "email code", "verify email", "verification code", "didn't receive email"],
        "answer": "Check your inbox (and spam folder). The verification link/code is valid for 60 minutes. If it expired, you can request a new one from the login dialog."
    },
    {
        "id": "push_notifications",
        "patterns": ["push notifications", "notifications", "alerts", "updates"],
        "answer": "Push notifications can be enabled in your profile settings. You'll receive updates when your issues change status."
    }
]

class ChatIn(BaseModel):
    session_id: str
    message: str
    user: Optional[dict] = None

class ChatOut(BaseModel):
    reply: str
    suggestions: list[str] = []
    state: dict = {}

def extract_issue_id(text: str) -> Optional[int]:
    patterns = [
        r"#?(\d{1,10})",
        r"issue\s*#?(\d{1,10})",
        r"complaint\s*#?(\d{1,10})",
        r"ticket\s*#?(\d{1,10})"
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                return int(m.group(1))
            except:
                pass
    return None

def match_faq(text: str) -> Optional[dict]:
    text_lower = text.lower()
    best_match = None
    best_score = 0
    
    for faq in FAQ_ENTRIES:
        for pattern in faq["patterns"]:
            if pattern in text_lower:
                score = len(pattern) / len(text_lower) if text_lower else 0
                if score > best_score:
                    best_score = score
                    best_match = faq
                    break
    
    if not best_match:
        all_patterns = " ".join([p for faq in FAQ_ENTRIES for p in faq["patterns"]])
        close = get_close_matches(text_lower, all_patterns.split(), n=1, cutoff=0.6)
        if close:
            for faq in FAQ_ENTRIES:
                if any(close[0] in p for p in faq["patterns"]):
                    best_match = faq
                    break
    
    return best_match

def handle_issue_status(issue_id: int, db: Session, user: Optional[User], allow_anonymous: bool) -> ChatOut:
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    if not issue:
        return ChatOut(
            reply=f"I couldn't find any issue with number #{issue_id}. Please check the number.",
            suggestions=["Show my issues", "How do I find my issue number?"]
        )
    
    can_view = False
    if allow_anonymous:
        can_view = True
    elif user:
        if issue.created_by_id == user.id:
            can_view = True
        elif user.role.value in ["admin", "super_admin"]:
            can_view = True
        elif user.role.value == "staff" and issue.assigned_to_id == user.id:
            can_view = True
    
    if not can_view:
        return ChatOut(
            reply="For privacy reasons, I can only show details for your own issues or if you're staff. Please login with the account that created this issue.",
            suggestions=["Login help", "Show my issues"]
        )
    
    status_map = {
        "pending": "Pending (waiting to be picked up)",
        "in_progress": "In Progress (someone is working on it)",
        "resolved": "Resolved (marked as fixed)"
    }
    status_text = status_map.get(issue.status.value, issue.status.value.replace("_", " ").title())
    
    reply = (
        f"Issue #{issue.id}: {issue.title}\n"
        f"Status: {status_text}\n"
        f"Location: {issue.address or issue.state_code or 'Not specified'}\n"
        f"Created: {issue.created_at.strftime('%Y-%m-%d %H:%M') if issue.created_at else 'Unknown'}"
    )
    
    return ChatOut(
        reply=reply,
        suggestions=["View full details", "Show my issues", "What does 'in progress' mean?"],
        state={"action": "view_issue", "issue_id": issue_id}
    )

def handle_my_issues(db: Session, user: Optional[User]) -> ChatOut:
    if not user:
        return ChatOut(
            reply="To see your issues, please login first.",
            suggestions=["Login help", "How do I report an issue?"]
        )
    
    issues = db.query(Issue).filter(Issue.created_by_id == user.id).order_by(Issue.created_at.desc()).all()
    total = len(issues)
    
    if not issues:
        reply = "You don't have any issues yet. You can report one from the dashboard."
    else:
        open_count = sum(1 for i in issues if i.status != IssueStatus.resolved)
        last = issues[0]
        status_text = last.status.value.replace("_", " ").title()
        reply = (
            f"You have {total} issue{'s' if total != 1 else ''} ({open_count} open). "
            f"Most recent: #{last.id} – {last.title} [{status_text}]."
        )
    
    suggestions = ["Check status of an issue", "How do I report an issue?"]
    if issues:
        suggestions.insert(0, f"Check status of issue #{issues[0].id}")
    
    return ChatOut(reply=reply, suggestions=suggestions)

def _get_app_settings_safe(db: Session):
    """Safely get AppSettings, handling missing columns."""
    try:
        settings = db.query(AppSettings).first()
        return settings
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        try:
            from sqlalchemy import text
            result = db.execute(text("SELECT allow_anonymous_reporting FROM app_settings LIMIT 1")).mappings().first()
            if result:
                class SimpleSettings:
                    allow_anonymous_reporting = result.get('allow_anonymous_reporting', False)
                return SimpleSettings()
        except Exception:
            pass
        return None

@router.post("/chat", response_model=ChatOut)
def chat(payload: ChatIn, db: Session = Depends(get_db), user: Optional[User] = Depends(get_optional_user)):
    text = payload.message.strip().lower()
    
    settings = _get_app_settings_safe(db)
    allow_anonymous = getattr(settings, 'allow_anonymous_reporting', False) if settings else False
    
    issue_id = extract_issue_id(text)
    if issue_id:
        return handle_issue_status(issue_id, db, user, allow_anonymous)
    
    if "my issues" in text or "my complaints" in text or "show my issues" in text:
        return handle_my_issues(db, user)
    
    if "status" in text and ("issue" in text or "ticket" in text or "complaint" in text):
        return ChatOut(
            reply="Sure, tell me the issue number (for example: #123 or issue 123).",
            suggestions=["Issue #123", "I don't know my issue number", "Show my issues"],
            state={"expecting_issue_id": True}
        )
    
    report_keywords = ["how to report", "how do i report", "report an issue", "submit", "raise an issue", "file a complaint", "new issue", "create issue"]
    if any(k in text for k in report_keywords) and "my issues" not in text and "show my" not in text:
        if not user and not allow_anonymous:
            return ChatOut(
                reply="To report an issue, you need to login first. Click the 'Sign in' button at the top right.",
                suggestions=["Open login", "How do I login?", "What can I report?"],
                state={"action": "open_login", "open_report_after_auth": True}
            )
        return ChatOut(
            reply="To report an issue, click the 'Report an issue' button on the dashboard. You'll select a category, location on the map, and optionally upload photos. You can report anonymously if enabled, or login for better tracking.",
            suggestions=["What can I report?", "Do I need to login to report?", "Report An Issue"],
            state={"action": "open_report"}
        )
    
    if "anonymous" in text:
        reply = "Anonymous reporting is " + ("enabled" if allow_anonymous else "disabled") + "."
        if allow_anonymous:
            reply += " You can report issues without logging in."
        else:
            reply += " Please login to report issues."
        return ChatOut(
            reply=reply,
            suggestions=["Login help", "How do I report an issue?"]
        )
    
    if "login" in text or "sign in" in text or "log in" in text:
        return ChatOut(
            reply="To login, click the 'Sign in' button at the top right. If you haven't verified your email yet, you'll receive a verification link/code by email.",
            suggestions=["I didn't receive verification email", "How to reset password", "Open login"],
            state={"action": "open_login"}
        )
    
    if "verification" in text or "code" in text or "verify" in text:
        return ChatOut(
            reply="Check your inbox (and spam folder). The verification link/code is valid for 60 minutes. If it expired, you can request a new one from the login dialog.",
            suggestions=["Resend verification email", "How to change my email"]
        )
    
    faq = match_faq(text)
    if faq:
        return ChatOut(
            reply=faq["answer"],
            suggestions=["Anything else?", "How do I report an issue?"]
        )
    
    return ChatOut(
        reply=(
            "I'm not sure I understood that yet.\n\n"
            "I can help you with:\n"
            "• How to report an issue\n"
            "• Checking issue status\n"
            "• Viewing your issues\n"
            "• Understanding statuses and notifications"
        ),
        suggestions=[
            "How do I report an issue?",
            "Check status of an issue",
            "Show my issues"
        ]
    )
