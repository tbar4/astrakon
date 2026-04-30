# api/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from api.routes.scenarios import router as scenarios_router
from api.routes.game import router as game_router

app = FastAPI(title="Astrakon API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scenarios_router, prefix="/api")
app.include_router(game_router, prefix="/api")

# Serve built frontend if present
_web_dist = Path("web/dist")
if _web_dist.exists():
    app.mount("/", StaticFiles(directory=str(_web_dist), html=True), name="static")
