from fastapi import HTTPException

from piios_backend.schemas.common import ADVISORY_BOUNDARY


def assert_advisory_only() -> None:
    if "order placement" in ADVISORY_BOUNDARY.lower() and "broker integration" in ADVISORY_BOUNDARY.lower():
        return
    raise HTTPException(status_code=500, detail="Product boundary misconfigured")
