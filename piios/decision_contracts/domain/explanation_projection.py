from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecommendationExplanation:
    recommendation_action: str
    recommendation_priority: str
    total_confidence: float
    confidence_dimensions: dict[str, float]
    primary_supporting_reasons: tuple[dict[str, str], ...]
    primary_limiting_reasons: tuple[dict[str, str], ...]
    material_risk_warnings: tuple[dict[str, str], ...]
    portfolio_suitability_summary: dict[str, str]
    position_size_range: dict[str, float] | None
    execution_considerations: tuple[dict[str, str], ...]
    monitoring_triggers: tuple[dict[str, str], ...]
    engine_version: str
    policy_version: str
    input_snapshot_timestamp: str
    trace_id: str
    proposal_version_id: str
    summary_text: str

    def __post_init__(self) -> None:
        for field_name, value in (
            ("recommendation_action", self.recommendation_action),
            ("recommendation_priority", self.recommendation_priority),
            ("engine_version", self.engine_version),
            ("policy_version", self.policy_version),
            ("input_snapshot_timestamp", self.input_snapshot_timestamp),
            ("trace_id", self.trace_id),
            ("proposal_version_id", self.proposal_version_id),
            ("summary_text", self.summary_text),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} must not be empty")
        if self.total_confidence < 0.0 or self.total_confidence > 1.0:
            raise ValueError("total_confidence must be within [0.0, 1.0]")
