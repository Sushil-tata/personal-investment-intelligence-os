from fastapi import APIRouter


router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("")
def get_risk() -> dict:
    return {
        "max_position_pct": 5,
        "max_tactical_pct": 10,
        "max_single_ticker_pct": 7,
        "advisory_only": True,
    }
