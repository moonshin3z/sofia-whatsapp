import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.webhook import router as webhook_router
from routers.api import router as api_router

logging.basicConfig(level=logging.WARNING)

app = FastAPI(
    title="Sofía AI — WhatsApp Dental Bot",
    description=(
        "Backend for Sofía, a virtual dental clinic receptionist on WhatsApp. "
        "Connects Twilio → Claude (tool use) → Cal.com for automated booking."
    ),
    version="1.0.0",
)

# CORS — open for demo/portfolio; restrict allow_origins in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook_router)  # POST /webhook, GET /health
app.include_router(api_router)      # GET /api/*


@app.get("/")
async def root() -> dict:
    return {
        "name": "Sofía AI WhatsApp Backend",
        "status": "running",
        "docs": "/docs",
    }
