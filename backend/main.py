"""
main.py

LemonCheck FastAPI application entry point.

Initializes the FastAPI app, registers all routers, and configures:
  - CORS middleware (allows requests from the Vite frontend in dev + Vercel in prod)
  - Global exception handlers for consistent error response shapes
  - Health check endpoint at GET /health

Run locally with:
  uvicorn main:app --reload --port 8000

The app is deployed to Railway. Railway reads the PORT env var; uvicorn
is configured to respect it via the Procfile / Railway start command.
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import analysis, auth, demo

app = FastAPI(
    title="LemonCheck API",
    description="AI-powered used car deal analyzer — backend API",
    version="0.1.0",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Allow the Vite dev server and Vercel deployment to call this API.
# In production, tighten this to the exact Vercel domain.
allowed_origins = [
    "http://localhost:5173",           # Vite dev server
    "http://localhost:3000",           # Alternative local
    "https://lemon-check.vercel.app",  # Production Vercel URL (hardcoded fallback)
    os.getenv("FRONTEND_URL", ""),     # Production Vercel URL (set in Railway env)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in allowed_origins if o],
    allow_origin_regex=r"https://lemon-check.*\.vercel\.app",  # Covers preview deploys
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(analysis.router, tags=["analysis"])
app.include_router(demo.router, tags=["demo"])
app.include_router(auth.router, tags=["auth"])

# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["health"])
async def health_check():
    """Simple liveness probe used by Railway to verify the app is running."""
    return {"status": "ok", "service": "lemoncheck-api"}
