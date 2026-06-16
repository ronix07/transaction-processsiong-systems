"""initial schema: jobs, transactions, job_summaries

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("row_count_raw", sa.Integer(), nullable=False),
        sa.Column("row_count_clean", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_jobs_status", "jobs", ["status"])

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("txn_id", sa.String(50), nullable=True),
        sa.Column("date", sa.String(10), nullable=True),
        sa.Column("merchant", sa.String(255), nullable=True),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(10), nullable=True),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("account_id", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_anomaly", sa.Boolean(), nullable=False),
        sa.Column("anomaly_reason", sa.Text(), nullable=True),
        sa.Column("llm_category", sa.String(50), nullable=True),
        sa.Column("llm_raw_response", sa.Text(), nullable=True),
        sa.Column("llm_failed", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_transactions_job_id", "transactions", ["job_id"])

    op.create_table(
        "job_summaries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("total_spend_inr", sa.Float(), nullable=False),
        sa.Column("total_spend_usd", sa.Float(), nullable=False),
        sa.Column("top_merchants", sa.JSON(), nullable=False),
        sa.Column("anomaly_count", sa.Integer(), nullable=False),
        sa.Column("narrative", sa.Text(), nullable=True),
        sa.Column("risk_level", sa.String(10), nullable=True),
    )
    op.create_index("ix_job_summaries_job_id", "job_summaries", ["job_id"])


def downgrade() -> None:
    op.drop_table("job_summaries")
    op.drop_table("transactions")
    op.drop_table("jobs")
