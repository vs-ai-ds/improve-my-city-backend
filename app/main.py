from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import cors_origins_list
from app.routers import issues

app = FastAPI(title="Improve My City API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"ok": True}

app.include_router(issues.router)
