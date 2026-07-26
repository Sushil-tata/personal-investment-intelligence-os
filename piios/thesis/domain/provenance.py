from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ProvenanceRecord:
    provenance_id: str
    entity_type: str
    entity_id: str
    action: str
    actor_type: str
    actor_reference: str
    ingestion_method: str
    source_system: str
    extraction_method: str
    model_name: str | None
    model_version: str | None
    payload_hash: str | None
    created_at: datetime
