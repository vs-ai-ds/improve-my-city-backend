# File: app\main.py
# Project: improve-my-city-backend
# Auto-added for reference

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from app.core.config import cors_origins_list, settings
from app.core.ratelimit import limiter
from app.routers import auth, issues, settings as settings_router, issue_types, bot, issues_stats
from app.routers import users, regions, push_subscriptions
from app.routers import public_issue_types
from app.routers import admin_users

app = FastAPI(title="Improve My City API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins_list(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"ok": True}

app.include_router(auth.router)
app.include_router(issues.router)
app.include_router(settings_router.router)
app.include_router(issue_types.router)
app.include_router(bot.router)
app.include_router(issues_stats.router)
app.include_router(users.router)
app.include_router(regions.router)
app.include_router(push_subscriptions.router)
app.include_router(public_issue_types.router)
app.include_router(admin_users.router)