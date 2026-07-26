"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-06-03
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("portfolios", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(), nullable=False), sa.Column("owner", sa.String(), nullable=False))
    op.create_table("accounts", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("portfolio_id", sa.Integer(), nullable=False), sa.Column("provider", sa.String(), nullable=False), sa.Column("currency", sa.String(), nullable=False))
    op.create_table("assets", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("ticker", sa.String(), nullable=False), sa.Column("name", sa.String(), nullable=False), sa.Column("asset_class", sa.String(), nullable=False))
    op.create_table("holdings", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("account_id", sa.Integer(), nullable=False), sa.Column("asset_id", sa.Integer(), nullable=False), sa.Column("quantity", sa.Float(), nullable=False), sa.Column("market_value", sa.Float(), nullable=False), sa.Column("bucket", sa.String(), nullable=True))
    op.create_table("transactions", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("account_id", sa.Integer(), nullable=False), sa.Column("asset_id", sa.Integer(), nullable=False), sa.Column("transaction_type", sa.String(), nullable=False), sa.Column("quantity", sa.Float(), nullable=False), sa.Column("price", sa.Float(), nullable=False), sa.Column("timestamp", sa.String(), nullable=False))
    op.create_table("watchlist", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("ticker", sa.String(), nullable=False), sa.Column("note", sa.String(), nullable=False), sa.Column("bucket", sa.String(), nullable=True))
    op.create_table("market_prices", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("asset_id", sa.Integer(), nullable=False), sa.Column("price", sa.Float(), nullable=False), sa.Column("timestamp", sa.String(), nullable=False))
    op.create_table("fundamentals", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("asset_id", sa.Integer(), nullable=False), sa.Column("payload_json", sa.String(), nullable=False), sa.Column("timestamp", sa.String(), nullable=False))
    op.create_table("macro_indicators", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("key", sa.String(), nullable=False), sa.Column("value", sa.Float(), nullable=False), sa.Column("timestamp", sa.String(), nullable=False))
    op.create_table("research_documents", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("title", sa.String(), nullable=False), sa.Column("content", sa.Text(), nullable=False), sa.Column("source", sa.String(), nullable=False), sa.Column("url", sa.String(), nullable=True), sa.Column("timestamp", sa.String(), nullable=False), sa.Column("credibility_score", sa.Float(), nullable=False), sa.Column("extracted_entities", sa.Text(), nullable=False), sa.Column("related_ticker_theme", sa.String(), nullable=False))
    op.create_table("source_scores", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("source", sa.String(), nullable=False), sa.Column("score", sa.Float(), nullable=False), sa.Column("timestamp", sa.String(), nullable=False))
    op.create_table("stock_scores", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("ticker", sa.String(), nullable=False), sa.Column("total_score", sa.Float(), nullable=False), sa.Column("bucket", sa.String(), nullable=True), sa.Column("timestamp", sa.String(), nullable=False))
    op.create_table("recommendations", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("recommendation_id", sa.String(), nullable=False), sa.Column("ticker", sa.String(), nullable=False), sa.Column("bucket", sa.String(), nullable=True), sa.Column("bull_case", sa.Text(), nullable=False), sa.Column("bear_case", sa.Text(), nullable=False), sa.Column("why_now", sa.Text(), nullable=False), sa.Column("why_not_now", sa.Text(), nullable=False), sa.Column("thesis_invalidation_trigger", sa.Text(), nullable=False), sa.Column("position_size_suggestion", sa.Text(), nullable=False), sa.Column("time_horizon", sa.String(), nullable=False), sa.Column("confidence_score", sa.Float(), nullable=False), sa.Column("data_freshness_timestamp", sa.String(), nullable=False), sa.Column("source_links", sa.Text(), nullable=False), sa.Column("rationale", sa.Text(), nullable=False), sa.Column("data_source", sa.String(), nullable=False), sa.Column("model_version", sa.String(), nullable=False), sa.Column("advisory_only", sa.Boolean(), nullable=False), sa.Column("created_at", sa.String(), nullable=False))
    op.create_table("tactical_signals", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("signal_id", sa.String(), nullable=False), sa.Column("ticker", sa.String(), nullable=False), sa.Column("bucket", sa.String(), nullable=True), sa.Column("status", sa.String(), nullable=False), sa.Column("entry_zone", sa.String(), nullable=False), sa.Column("invalidation", sa.String(), nullable=False), sa.Column("target", sa.String(), nullable=False), sa.Column("advisory_only", sa.Boolean(), nullable=False), sa.Column("created_at", sa.String(), nullable=False))
    op.create_table("risk_profiles", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("max_position_pct", sa.Float(), nullable=False), sa.Column("max_tactical_pct", sa.Float(), nullable=False), sa.Column("max_single_ticker_pct", sa.Float(), nullable=False))
    op.create_table("journal_entries", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("entry_id", sa.String(), nullable=False), sa.Column("ticker", sa.String(), nullable=False), sa.Column("notes", sa.Text(), nullable=False), sa.Column("outcome", sa.String(), nullable=False), sa.Column("bucket", sa.String(), nullable=True), sa.Column("created_at", sa.String(), nullable=False))
    op.create_table("audit_logs", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("event_type", sa.String(), nullable=False), sa.Column("details", sa.Text(), nullable=False), sa.Column("timestamp", sa.String(), nullable=False))
    op.create_table("graph_runs", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("run_id", sa.String(), nullable=False), sa.Column("ticker", sa.String(), nullable=False), sa.Column("status", sa.String(), nullable=False), sa.Column("requested_by", sa.String(), nullable=False), sa.Column("created_at", sa.String(), nullable=False))
    op.create_table("graph_node_outputs", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("run_id", sa.String(), nullable=False), sa.Column("node_name", sa.String(), nullable=False), sa.Column("output_json", sa.Text(), nullable=False), sa.Column("timestamp", sa.String(), nullable=False))


def downgrade() -> None:
    for table in [
        "graph_node_outputs",
        "graph_runs",
        "audit_logs",
        "journal_entries",
        "risk_profiles",
        "tactical_signals",
        "recommendations",
        "stock_scores",
        "source_scores",
        "research_documents",
        "macro_indicators",
        "fundamentals",
        "market_prices",
        "watchlist",
        "transactions",
        "holdings",
        "assets",
        "accounts",
        "portfolios",
    ]:
        op.drop_table(table)
