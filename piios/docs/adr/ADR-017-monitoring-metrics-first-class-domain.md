# ADR-017: Monitoring Metrics as First-Class Domain Entities

## Status
Proposed

## Context
Thesis durability requires explicit monitored conditions and repeatable review triggers.

## Decision
MonitoringMetric and MetricObservation are persisted first-class entities linked to ThesisClaim.

## Alternatives Considered
- Keep monitoring points as narrative bullet lists.
- Compute metric checks ad hoc in report generation.

## Consequences
- Deterministic review inputs and longitudinal monitoring history.
- Additional ingestion and data quality controls required.

## Implementation Implications
- Threshold schema and evaluation result model.
- Observation freshness and source lineage metadata.

## Migration Implications
- Legacy theses gain optional metric templates during phased onboarding.

## Open Questions
- Ownership of qualitative metric scoring calibration.
