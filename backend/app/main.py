from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
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
