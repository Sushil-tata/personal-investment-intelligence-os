"""add identity master tables for company/security/listing

Revision ID: 0005_identity_master_tables
Revises: 0004_portfolio_layers
Create Date: 2026-07-26
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_identity_master_tables"
down_revision = "0004_portfolio_layers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "identity_companies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("company_id", sa.String(), nullable=False),
        sa.Column("legal_name", sa.String(), nullable=False),
        sa.Column("common_name", sa.String(), nullable=True),
        sa.Column("company_type", sa.String(), nullable=False),
        sa.Column("jurisdiction_of_incorporation", sa.String(length=2), nullable=False),
        sa.Column("primary_economic_country", sa.String(length=2), nullable=False),
        sa.Column("sector", sa.String(), nullable=True),
        sa.Column("industry", sa.String(), nullable=True),
        sa.Column("active_from", sa.String(), nullable=False),
        sa.Column("active_to", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.UniqueConstraint("company_id", name="uq_identity_companies_company_id"),
    )
    op.create_index("ix_identity_companies_legal_name", "identity_companies", ["legal_name"])
    op.create_index("ix_identity_companies_status", "identity_companies", ["status"])
    op.create_index("ix_identity_companies_effective_dates", "identity_companies", ["active_from", "active_to"])

    op.create_table(
        "identity_securities",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("security_id", sa.String(), nullable=False),
        sa.Column("issuer_company_id", sa.String(), nullable=True),
        sa.Column("issuer_name", sa.String(), nullable=True),
        sa.Column("security_type", sa.String(), nullable=False),
        sa.Column("security_name", sa.String(), nullable=False),
        sa.Column("issue_currency", sa.String(length=3), nullable=False),
        sa.Column("issue_date", sa.String(), nullable=True),
        sa.Column("maturity_date", sa.String(), nullable=True),
        sa.Column("share_class_or_seniority", sa.String(), nullable=True),
        sa.Column("economic_exposure_type", sa.String(), nullable=True),
        sa.Column("active_from", sa.String(), nullable=False),
        sa.Column("active_to", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.UniqueConstraint("security_id", name="uq_identity_securities_security_id"),
        sa.ForeignKeyConstraint(["issuer_company_id"], ["identity_companies.company_id"], name="fk_identity_security_company_id"),
    )
    op.create_index("ix_identity_securities_company_id", "identity_securities", ["issuer_company_id"])
    op.create_index("ix_identity_securities_status", "identity_securities", ["status"])
    op.create_index("ix_identity_securities_effective_dates", "identity_securities", ["active_from", "active_to"])

    op.create_table(
        "identity_listing_instruments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("listing_id", sa.String(), nullable=False),
        sa.Column("security_id", sa.String(), nullable=False),
        sa.Column("exchange_code", sa.String(), nullable=False),
        sa.Column("ticker_source", sa.String(), nullable=False),
        sa.Column("ticker_canonical", sa.String(), nullable=False),
        sa.Column("trading_currency", sa.String(length=3), nullable=False),
        sa.Column("listing_country", sa.String(length=2), nullable=False),
        sa.Column("is_primary_listing", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("lot_size", sa.Float(), nullable=True),
        sa.Column("price_source_symbol", sa.String(), nullable=True),
        sa.Column("active_from", sa.String(), nullable=False),
        sa.Column("active_to", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.UniqueConstraint("listing_id", name="uq_identity_listing_listing_id"),
        sa.ForeignKeyConstraint(["security_id"], ["identity_securities.security_id"], name="fk_identity_listing_security_id"),
    )
    op.create_index("ix_identity_listing_security_id", "identity_listing_instruments", ["security_id"])
    op.create_index("ix_identity_listing_exchange_ticker", "identity_listing_instruments", ["exchange_code", "ticker_canonical"])
    op.create_index("ix_identity_listing_status", "identity_listing_instruments", ["status"])
    op.create_index("ix_identity_listing_effective_dates", "identity_listing_instruments", ["active_from", "active_to"])

    op.create_table(
        "identity_security_identifiers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("identifier_id", sa.String(), nullable=False),
        sa.Column("entity_scope", sa.String(), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("identifier_type", sa.String(), nullable=False),
        sa.Column("identifier_value", sa.String(), nullable=False),
        sa.Column("provider_or_authority", sa.String(), nullable=False),
        sa.Column("active_from", sa.String(), nullable=False),
        sa.Column("active_to", sa.String(), nullable=True),
        sa.Column("verification_status", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.UniqueConstraint("identifier_id", name="uq_identity_identifiers_identifier_id"),
    )
    op.create_index(
        "ix_identity_identifiers_lookup",
        "identity_security_identifiers",
        ["identifier_type", "identifier_value", "provider_or_authority"],
    )
    op.create_index("ix_identity_identifiers_scope", "identity_security_identifiers", ["entity_scope", "entity_id"])
    op.create_index("ix_identity_identifiers_effective_dates", "identity_security_identifiers", ["active_from", "active_to"])

    op.create_table(
        "identity_ticker_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("ticker_history_id", sa.String(), nullable=False),
        sa.Column("listing_id", sa.String(), nullable=False),
        sa.Column("exchange_code", sa.String(), nullable=False),
        sa.Column("ticker_source", sa.String(), nullable=False),
        sa.Column("ticker_canonical", sa.String(), nullable=False),
        sa.Column("active_from", sa.String(), nullable=False),
        sa.Column("active_to", sa.String(), nullable=True),
        sa.Column("change_reason", sa.String(), nullable=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("verification_status", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.UniqueConstraint("ticker_history_id", name="uq_identity_ticker_history_id"),
        sa.ForeignKeyConstraint(["listing_id"], ["identity_listing_instruments.listing_id"], name="fk_identity_ticker_listing_id"),
    )
    op.create_index("ix_identity_ticker_listing", "identity_ticker_history", ["listing_id"])
    op.create_index("ix_identity_ticker_lookup", "identity_ticker_history", ["exchange_code", "ticker_canonical"])
    op.create_index("ix_identity_ticker_effective_dates", "identity_ticker_history", ["active_from", "active_to"])

    op.create_table(
        "identity_security_relationships",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("relationship_id", sa.String(), nullable=False),
        sa.Column("source_scope", sa.String(), nullable=False),
        sa.Column("source_entity_id", sa.String(), nullable=False),
        sa.Column("target_scope", sa.String(), nullable=False),
        sa.Column("target_entity_id", sa.String(), nullable=False),
        sa.Column("relationship_type", sa.String(), nullable=False),
        sa.Column("conversion_ratio", sa.Float(), nullable=True),
        sa.Column("active_from", sa.String(), nullable=False),
        sa.Column("active_to", sa.String(), nullable=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("verification_status", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.UniqueConstraint("relationship_id", name="uq_identity_relationships_relationship_id"),
    )
    op.create_index("ix_identity_relationships_source", "identity_security_relationships", ["source_scope", "source_entity_id"])
    op.create_index("ix_identity_relationships_target", "identity_security_relationships", ["target_scope", "target_entity_id"])
    op.create_index("ix_identity_relationships_effective_dates", "identity_security_relationships", ["active_from", "active_to"])

    op.create_table(
        "identity_legacy_mappings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("mapping_id", sa.String(), nullable=False),
        sa.Column("legacy_source", sa.String(), nullable=False),
        sa.Column("legacy_record_id", sa.String(), nullable=False),
        sa.Column("legacy_asset_id", sa.String(), nullable=True),
        sa.Column("legacy_instrument_id", sa.String(), nullable=True),
        sa.Column("legacy_ticker", sa.String(), nullable=True),
        sa.Column("company_id", sa.String(), nullable=True),
        sa.Column("security_id", sa.String(), nullable=True),
        sa.Column("listing_id", sa.String(), nullable=True),
        sa.Column("resolution_status", sa.String(), nullable=False),
        sa.Column("provenance", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.UniqueConstraint("mapping_id", name="uq_identity_legacy_mapping_id"),
    )
    op.create_index("ix_identity_legacy_source_record", "identity_legacy_mappings", ["legacy_source", "legacy_record_id"])
    op.create_index("ix_identity_legacy_asset", "identity_legacy_mappings", ["legacy_asset_id"])
    op.create_index("ix_identity_legacy_ticker", "identity_legacy_mappings", ["legacy_ticker"])

    op.create_table(
        "identity_resolution_issues",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("issue_id", sa.String(), nullable=False),
        sa.Column("source_record_type", sa.String(), nullable=False),
        sa.Column("source_record_id", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("candidate_payload", sa.Text(), nullable=False),
        sa.Column("recommended_resolution", sa.String(), nullable=True),
        sa.Column("owner_decision", sa.String(), nullable=True),
        sa.Column("reviewer", sa.String(), nullable=True),
        sa.Column("reviewed_at", sa.String(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("resulting_mapping_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.UniqueConstraint("issue_id", name="uq_identity_resolution_issue_id"),
    )
    op.create_index("ix_identity_resolution_issue_status", "identity_resolution_issues", ["status"])
    op.create_index("ix_identity_resolution_issue_source", "identity_resolution_issues", ["source_record_type", "source_record_id"])


def downgrade() -> None:
    op.drop_index("ix_identity_resolution_issue_source", table_name="identity_resolution_issues")
    op.drop_index("ix_identity_resolution_issue_status", table_name="identity_resolution_issues")
    op.drop_table("identity_resolution_issues")

    op.drop_index("ix_identity_legacy_ticker", table_name="identity_legacy_mappings")
    op.drop_index("ix_identity_legacy_asset", table_name="identity_legacy_mappings")
    op.drop_index("ix_identity_legacy_source_record", table_name="identity_legacy_mappings")
    op.drop_table("identity_legacy_mappings")

    op.drop_index("ix_identity_relationships_effective_dates", table_name="identity_security_relationships")
    op.drop_index("ix_identity_relationships_target", table_name="identity_security_relationships")
    op.drop_index("ix_identity_relationships_source", table_name="identity_security_relationships")
    op.drop_table("identity_security_relationships")

    op.drop_index("ix_identity_ticker_effective_dates", table_name="identity_ticker_history")
    op.drop_index("ix_identity_ticker_lookup", table_name="identity_ticker_history")
    op.drop_index("ix_identity_ticker_listing", table_name="identity_ticker_history")
    op.drop_table("identity_ticker_history")

    op.drop_index("ix_identity_identifiers_effective_dates", table_name="identity_security_identifiers")
    op.drop_index("ix_identity_identifiers_scope", table_name="identity_security_identifiers")
    op.drop_index("ix_identity_identifiers_lookup", table_name="identity_security_identifiers")
    op.drop_table("identity_security_identifiers")

    op.drop_index("ix_identity_listing_effective_dates", table_name="identity_listing_instruments")
    op.drop_index("ix_identity_listing_status", table_name="identity_listing_instruments")
    op.drop_index("ix_identity_listing_exchange_ticker", table_name="identity_listing_instruments")
    op.drop_index("ix_identity_listing_security_id", table_name="identity_listing_instruments")
    op.drop_table("identity_listing_instruments")

    op.drop_index("ix_identity_securities_effective_dates", table_name="identity_securities")
    op.drop_index("ix_identity_securities_status", table_name="identity_securities")
    op.drop_index("ix_identity_securities_company_id", table_name="identity_securities")
    op.drop_table("identity_securities")

    op.drop_index("ix_identity_companies_effective_dates", table_name="identity_companies")
    op.drop_index("ix_identity_companies_status", table_name="identity_companies")
    op.drop_index("ix_identity_companies_legal_name", table_name="identity_companies")
    op.drop_table("identity_companies")
