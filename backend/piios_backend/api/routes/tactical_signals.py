from fastapi import APIRouter

from piios_backend.schemas.recommendation import TacticalSignal
from piios_backend.services.in_memory_store import store
from piios_backend.services.live_feeds import live_feeds


router = APIRouter(prefix="/tactical-signals", tags=["tactical-signals"])


@router.get("", response_model=list[TacticalSignal])
def get_tactical_signals() -> list[TacticalSignal]:
    live_feeds.refresh_tactical_signals(store.signals)
    return store.signals
