from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from piios.decision_contracts.application.scoring_components import (
    ComponentOrientation,
    ComponentScore,
    PortfolioContextSnapshot,
    RecommendationEngineInput,
)
from piios.decision_contracts.domain.enums import Priority, RecommendationAction
from piios.decision_contracts.domain.value_objects import PositionSizeRange, RecommendationPriority


@dataclass(frozen=True)
class WeightedComponentScore:
    component_key: str
    weight: float
    value: float
    normalized_value: float
    contribution: float
    orientation: ComponentOrientation


@dataclass(frozen=True)
class StrategyResult:
    strategy_key: str
    overall_score: float
    action: RecommendationAction
    position_size_range: PositionSizeRange | None
    priority: RecommendationPriority
    confidence_label: str
    required_human_review: bool
    applied_rules: tuple[str, ...]
    component_breakdown: tuple[WeightedComponentScore, ...]


class WeightedRecommendationStrategy:
    def __init__(
        self,
        strategy_key: str,
        display_name: str,
        component_weights: dict[str, float],
        buy_threshold: float,
        add_threshold: float,
        hold_threshold: float,
        watch_threshold: float,
        risk_appetite_multiplier: float,
        mandatory_review_score_threshold: float,
        mandatory_review_penalty_threshold: float,
    ) -> None:
        self.strategy_key = strategy_key
        self.display_name = display_name
        self.component_weights = component_weights
        self.buy_threshold = buy_threshold
        self.add_threshold = add_threshold
        self.hold_threshold = hold_threshold
        self.watch_threshold = watch_threshold
        self.risk_appetite_multiplier = risk_appetite_multiplier
        self.mandatory_review_score_threshold = mandatory_review_score_threshold
        self.mandatory_review_penalty_threshold = mandatory_review_penalty_threshold

    def evaluate(self, data: RecommendationEngineInput, scores: tuple[ComponentScore, ...]) -> StrategyResult:
        total_weight = 0.0
        weighted_sum = 0.0
        breakdown: list[WeightedComponentScore] = []
        score_by_key = {score.component_key: score for score in scores}

        for score in scores:
            weight = self.component_weights.get(score.component_key, 0.0)
            if weight < 0.0:
                raise ValueError(f"negative weight for component {score.component_key}")
            normalized = score.value if score.orientation == ComponentOrientation.BENEFIT else 1.0 - score.value
            contribution = weight * normalized
            total_weight += weight
            weighted_sum += contribution
            breakdown.append(
                WeightedComponentScore(
                    component_key=score.component_key,
                    weight=round(weight, 6),
                    value=round(score.value, 6),
                    normalized_value=round(normalized, 6),
                    contribution=round(contribution, 6),
                    orientation=score.orientation,
                )
            )

        overall_score = round((weighted_sum / total_weight) if total_weight else 0.0, 6)
        action = self._resolve_action(overall_score, data.portfolio_context)
        position_size_range = self._resolve_position_size_range(action, data.portfolio_context)

        risk_penalty = score_by_key.get("risk_penalty")
        contradiction_penalty = score_by_key.get("contradiction_penalty")
        max_penalty = max(
            risk_penalty.value if risk_penalty else 0.0,
            contradiction_penalty.value if contradiction_penalty else 0.0,
        )

        required_human_review = (
            overall_score <= self.mandatory_review_score_threshold
            or max_penalty >= self.mandatory_review_penalty_threshold
        )

        priority = RecommendationPriority(
            level=_priority_level(overall_score, required_human_review),
            score=_priority_score(overall_score, required_human_review),
        )

        confidence_label = _confidence_label(overall_score)

        rules = (
            f"strategy={self.strategy_key}",
            f"weighted_sum={weighted_sum:.6f}",
            f"total_weight={total_weight:.6f}",
            f"overall_score={overall_score:.6f}",
            f"max_penalty={max_penalty:.6f}",
            f"required_human_review={required_human_review}",
        )

        return StrategyResult(
            strategy_key=self.strategy_key,
            overall_score=overall_score,
            action=action,
            position_size_range=position_size_range,
            priority=priority,
            confidence_label=confidence_label,
            required_human_review=required_human_review,
            applied_rules=rules,
            component_breakdown=tuple(
                sorted(breakdown, key=lambda row: (-row.contribution, row.component_key))
            ),
        )

    def governance_profile(self) -> dict[str, object]:
        return {
            "strategy_key": self.strategy_key,
            "display_name": self.display_name,
            "component_weights": {
                key: round(value, 6)
                for key, value in sorted(self.component_weights.items(), key=lambda row: row[0])
            },
            "buy_threshold": round(self.buy_threshold, 6),
            "add_threshold": round(self.add_threshold, 6),
            "hold_threshold": round(self.hold_threshold, 6),
            "watch_threshold": round(self.watch_threshold, 6),
            "risk_appetite_multiplier": round(self.risk_appetite_multiplier, 6),
            "mandatory_review_score_threshold": round(self.mandatory_review_score_threshold, 6),
            "mandatory_review_penalty_threshold": round(self.mandatory_review_penalty_threshold, 6),
        }

    def governance_hash(self) -> str:
        payload = json.dumps(self.governance_profile(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _resolve_action(self, overall_score: float, ctx: PortfolioContextSnapshot) -> RecommendationAction:
        if overall_score >= self.buy_threshold:
            return RecommendationAction.ADD if ctx.has_existing_position else RecommendationAction.BUY
        if overall_score >= self.add_threshold:
            return RecommendationAction.ADD if ctx.has_existing_position else RecommendationAction.BUY
        if overall_score >= self.hold_threshold:
            return RecommendationAction.HOLD if ctx.has_existing_position else RecommendationAction.WATCH
        if overall_score >= self.watch_threshold:
            return RecommendationAction.WATCH
        if not ctx.has_existing_position:
            return RecommendationAction.NO_ACTION
        return RecommendationAction.REDUCE if overall_score >= 0.2 else RecommendationAction.SELL

    def _resolve_position_size_range(
        self,
        action: RecommendationAction,
        ctx: PortfolioContextSnapshot,
    ) -> PositionSizeRange | None:
        if action not in (RecommendationAction.BUY, RecommendationAction.ADD):
            return None

        headroom = max(ctx.max_position_weight - ctx.current_weight, 0.0)
        if headroom <= 0.0:
            return None

        base_min = min(0.01 * self.risk_appetite_multiplier, headroom)
        base_max = min(0.05 * self.risk_appetite_multiplier, headroom)
        if base_max < base_min:
            base_max = base_min

        return PositionSizeRange(
            min_weight=round(base_min, 6),
            max_weight=round(base_max, 6),
        )


def default_recommendation_strategies() -> dict[str, WeightedRecommendationStrategy]:
    return {
        "conservative-v1": WeightedRecommendationStrategy(
            strategy_key="conservative-v1",
            display_name="Conservative",
            component_weights={
                "health_score": 0.22,
                "confidence_score": 0.18,
                "evidence_quality_score": 0.14,
                "evidence_freshness_score": 0.12,
                "contradiction_penalty": 0.16,
                "portfolio_alignment_score": 0.08,
                "risk_penalty": 0.08,
                "opportunity_bonus": 0.02,
            },
            buy_threshold=0.82,
            add_threshold=0.68,
            hold_threshold=0.50,
            watch_threshold=0.35,
            risk_appetite_multiplier=0.8,
            mandatory_review_score_threshold=0.45,
            mandatory_review_penalty_threshold=0.55,
        ),
        "balanced-v1": WeightedRecommendationStrategy(
            strategy_key="balanced-v1",
            display_name="Balanced",
            component_weights={
                "health_score": 0.20,
                "confidence_score": 0.16,
                "evidence_quality_score": 0.14,
                "evidence_freshness_score": 0.10,
                "contradiction_penalty": 0.14,
                "portfolio_alignment_score": 0.12,
                "risk_penalty": 0.08,
                "opportunity_bonus": 0.06,
            },
            buy_threshold=0.76,
            add_threshold=0.62,
            hold_threshold=0.46,
            watch_threshold=0.30,
            risk_appetite_multiplier=1.0,
            mandatory_review_score_threshold=0.40,
            mandatory_review_penalty_threshold=0.60,
        ),
        "aggressive-v1": WeightedRecommendationStrategy(
            strategy_key="aggressive-v1",
            display_name="Aggressive",
            component_weights={
                "health_score": 0.18,
                "confidence_score": 0.14,
                "evidence_quality_score": 0.10,
                "evidence_freshness_score": 0.08,
                "contradiction_penalty": 0.12,
                "portfolio_alignment_score": 0.14,
                "risk_penalty": 0.06,
                "opportunity_bonus": 0.18,
            },
            buy_threshold=0.70,
            add_threshold=0.56,
            hold_threshold=0.40,
            watch_threshold=0.28,
            risk_appetite_multiplier=1.3,
            mandatory_review_score_threshold=0.34,
            mandatory_review_penalty_threshold=0.70,
        ),
    }


def _priority_level(overall_score: float, required_human_review: bool) -> Priority:
    if required_human_review and overall_score < 0.35:
        return Priority.URGENT
    if overall_score >= 0.8 or overall_score <= 0.2:
        return Priority.HIGH
    if overall_score >= 0.55 or overall_score <= 0.35:
        return Priority.MEDIUM
    return Priority.LOW


def _priority_score(overall_score: float, required_human_review: bool) -> float:
    distance = abs(overall_score - 0.5) * 2.0
    if required_human_review:
        distance = max(distance, 0.7)
    return round(min(distance, 1.0), 6)


def _confidence_label(overall_score: float) -> str:
    if overall_score >= 0.75:
        return "High"
    if overall_score >= 0.45:
        return "Medium"
    return "Low"
