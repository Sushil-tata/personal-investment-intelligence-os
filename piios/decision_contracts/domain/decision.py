from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from piios.decision_contracts.domain.enums import DecisionState
from piios.decision_contracts.domain.value_objects import ActionProposal, PositionSizeRange


@dataclass(frozen=True)
class InvestmentDecision:
    decision_id: str
    proposal_version_id: str
    state: DecisionState
    reason_code: str
    decided_at: datetime
    reason_text: str | None = None
    decided_by: str | None = None
    preferred_alternative_target_key: str | None = None
    modified_action: ActionProposal | None = None
    modified_position_size: PositionSizeRange | None = None

    def __post_init__(self) -> None:
        if not self.decision_id.strip():
            raise ValueError("decision_id must not be empty")
        if not self.proposal_version_id.strip():
            raise ValueError("proposal_version_id must not be empty")
        if not self.reason_code.strip():
            raise ValueError("reason_code must not be empty")

        if self.state == DecisionState.MODIFIED and self.modified_action is None and self.modified_position_size is None:
            raise ValueError("MODIFIED decisions must provide modified_action or modified_position_size")

        if self.state != DecisionState.MODIFIED and (
            self.modified_action is not None or self.modified_position_size is not None
        ):
            raise ValueError("only MODIFIED decisions may provide modified_action or modified_position_size")

        if self.state == DecisionState.OVERRIDDEN and not (self.preferred_alternative_target_key or "").strip():
            raise ValueError("OVERRIDDEN decisions must provide preferred_alternative_target_key")

        if self.state != DecisionState.OVERRIDDEN and self.preferred_alternative_target_key is not None:
            raise ValueError("preferred_alternative_target_key is only allowed for OVERRIDDEN decisions")
