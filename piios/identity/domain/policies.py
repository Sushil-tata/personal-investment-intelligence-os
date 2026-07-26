from __future__ import annotations

from datetime import date

from .entities import ListingInstrument, SecurityIdentifier, SecurityRelationship, TickerHistoryRecord
from .enums import RelationshipType
from .exceptions import (
    DuplicateActiveIdentifierError,
    InvalidRelationshipError,
    OverlappingTickerHistoryError,
)


def _overlap(a_from: date, a_to: date | None, b_from: date, b_to: date | None) -> bool:
    a_end = a_to or date.max
    b_end = b_to or date.max
    return a_from <= b_end and b_from <= a_end


def ensure_one_primary_listing(listings: list[ListingInstrument], as_of: date) -> None:
    active_primary = [
        listing
        for listing in listings
        if listing.is_primary_listing and listing.active_range.contains(as_of)
    ]
    if len(active_primary) > 1:
        raise InvalidRelationshipError("multiple active primary listings for the same security")


def validate_identifier_uniqueness(existing: list[SecurityIdentifier], incoming: SecurityIdentifier) -> None:
    for record in existing:
        if (
            record.scope == incoming.scope
            and record.entity_id == incoming.entity_id
            and record.identifier_type == incoming.identifier_type
            and record.identifier_value.value == incoming.identifier_value.value
            and _overlap(
                record.active_range.active_from,
                record.active_range.active_to,
                incoming.active_range.active_from,
                incoming.active_range.active_to,
            )
        ):
            raise DuplicateActiveIdentifierError("duplicate active identifier in overlapping effective range")


def validate_ticker_history_overlap(existing: list[TickerHistoryRecord], incoming: TickerHistoryRecord) -> None:
    for record in existing:
        if (
            record.listing_id == incoming.listing_id
            and record.exchange_code.value == incoming.exchange_code.value
            and record.ticker.canonical_value == incoming.ticker.canonical_value
            and _overlap(
                record.active_range.active_from,
                record.active_range.active_to,
                incoming.active_range.active_from,
                incoming.active_range.active_to,
            )
        ):
            raise OverlappingTickerHistoryError("overlapping ticker history for listing/exchange/ticker")


def validate_relationship(existing: list[SecurityRelationship], incoming: SecurityRelationship) -> None:
    if incoming.source_scope == incoming.target_scope and incoming.source_entity_id == incoming.target_entity_id:
        raise InvalidRelationshipError("self-relationship is not allowed")

    for row in existing:
        if (
            row.source_scope == incoming.source_scope
            and row.source_entity_id == incoming.source_entity_id
            and row.target_scope == incoming.target_scope
            and row.target_entity_id == incoming.target_entity_id
            and row.relationship_type == incoming.relationship_type
            and _overlap(
                row.active_range.active_from,
                row.active_range.active_to,
                incoming.active_range.active_from,
                incoming.active_range.active_to,
            )
        ):
            raise InvalidRelationshipError("duplicate overlapping relationship")

    contradictory_pairs = {
        (RelationshipType.SUCCESSOR_OF, RelationshipType.PREDECESSOR_OF),
        (RelationshipType.PREDECESSOR_OF, RelationshipType.SUCCESSOR_OF),
    }
    for row in existing:
        if (
            row.source_scope == incoming.source_scope
            and row.source_entity_id == incoming.source_entity_id
            and row.target_scope == incoming.target_scope
            and row.target_entity_id == incoming.target_entity_id
            and (row.relationship_type, incoming.relationship_type) in contradictory_pairs
            and _overlap(
                row.active_range.active_from,
                row.active_range.active_to,
                incoming.active_range.active_from,
                incoming.active_range.active_to,
            )
        ):
            raise InvalidRelationshipError("contradictory overlapping relationship")
