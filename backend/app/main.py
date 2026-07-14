from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import SessionLocal
from app.routers import (
    auth, dashboard, leave, payslips, profile, hr_requests, attendance,
    it_requests, chatbot, notifications, org,
)

app = FastAPI(
    title="HRFlow API",
    description="Employee Self-Service HR Portal backend (S2-C-01) — "
                 "FastAPI + PostgreSQL, matching the proposal's tech stack.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(leave.router)
app.include_router(payslips.router)
app.include_router(profile.router)
app.include_router(hr_requests.router)
app.include_router(attendance.router)
app.include_router(it_requests.router)
app.include_router(chatbot.router)
app.include_router(notifications.router)
app.include_router(org.router)


@app.on_event("startup")
def self_heal_chromadb():
    """
    Render's free tier has no persistent disk for the separately-hosted
    ChromaDB service, so a restart from inactivity silently wipes its
    indexed data (see rag_pipeline.reindex_all_from_postgres's docstring).
    Re-populating it from Postgres — the original chunk text's safe,
    permanent home — on every boot means a cold-started ChromaDB heals
    itself before the first chatbot query ever sees it empty, instead of
    requiring a manual re-upload each time.

    Deliberately best-effort: any failure here (ChromaDB unreachable, no
    Gemini API key configured, quota exhausted, etc.) is logged and
    swallowed rather than raised, since this must never prevent the API
    itself from starting.
    """
    from app import rag_pipeline
    db = SessionLocal()
    try:
        count = rag_pipeline.reindex_all_from_postgres(db)
        if count:
            print(f"[startup] Re-indexed {count} policy document(s) into ChromaDB after an empty collection was detected.")
    except Exception as e:
        print(f"[startup] ChromaDB self-heal skipped: {e}")
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {
        "service": "HRFlow API",
        "docs": "/docs",
        "health": "/health",
    }
