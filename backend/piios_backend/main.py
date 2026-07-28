from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from piios_backend.api.routes import (
    decision_contracts,
    graph,
    health,
    holdings,
    identity,
    journal,
    portfolio_layers,
    portfolio,
    recommendations,
    research,
    risk,
    scores,
    tactical_signals,
    theses,
    watchlist,
)
from piios_backend.core.config import settings
from piios_backend.core.database import engine, init_db
from piios_backend.core.guardrails import ADVISORY_BOUNDARY_TEXT
from piios_backend.jobs.scheduler import build_scheduler
from piios_backend.services.portfolio_layers import PortfolioLayersService
from piios_backend.services.theses import ThesisService


scheduler = build_scheduler()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    with Session(engine) as session:
        ThesisService(session).seed_canonical_thesis()
        PortfolioLayersService(session).seed_defaults()
    if not scheduler.running:
        scheduler.start()
    try:
        yield
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(portfolio.router, prefix=settings.api_prefix)
app.include_router(holdings.router, prefix=settings.api_prefix)
app.include_router(watchlist.router, prefix=settings.api_prefix)
app.include_router(research.router, prefix=settings.api_prefix)
app.include_router(scores.router, prefix=settings.api_prefix)
app.include_router(recommendations.router, prefix=settings.api_prefix)
app.include_router(tactical_signals.router, prefix=settings.api_prefix)
app.include_router(risk.router, prefix=settings.api_prefix)
app.include_router(journal.router, prefix=settings.api_prefix)
app.include_router(graph.router, prefix=settings.api_prefix)
app.include_router(theses.router, prefix=settings.api_prefix)
app.include_router(portfolio_layers.router, prefix=settings.api_prefix)
app.include_router(identity.router, prefix=settings.api_prefix)
app.include_router(decision_contracts.router, prefix=settings.api_prefix)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "product": settings.short_name,
        "boundary": ADVISORY_BOUNDARY_TEXT,
    }
