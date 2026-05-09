"""repair missing document skill tables

Revision ID: 0004_repair_doc_skills
Revises: 0003_study_flow
Create Date: 2026-05-09 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004_repair_doc_skills"
down_revision = "0003_study_flow"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def _foreign_key_exists(table_name: str, constraint_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(fk.get("name") == constraint_name for fk in inspector.get_foreign_keys(table_name))


def upgrade() -> None:
    if not _table_exists("document_skills"):
        op.create_table(
            "document_skills",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("document_id", sa.String(length=36), sa.ForeignKey("rag_documents.id"), nullable=False, unique=True),
            sa.Column("active_revision_id", sa.String(length=36), nullable=True),
            sa.Column("status", sa.String(length=50), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )

    if not _table_exists("document_skill_revisions"):
        op.create_table(
            "document_skill_revisions",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("document_skill_id", sa.String(length=36), sa.ForeignKey("document_skills.id"), nullable=False),
            sa.Column("revision_number", sa.Integer(), nullable=False),
            sa.Column("profile_json", sa.JSON(), nullable=False),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("extraction_model_name", sa.String(length=100), nullable=False),
            sa.Column("prompt_version", sa.String(length=100), nullable=False),
            sa.Column("source_digest", sa.String(length=64), nullable=True),
            sa.Column("update_reason", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    if not _foreign_key_exists("document_skills", "fk_document_skills_active_revision_id"):
        op.create_foreign_key(
            "fk_document_skills_active_revision_id",
            "document_skills",
            "document_skill_revisions",
            ["active_revision_id"],
            ["id"],
        )

    if not _table_exists("document_skill_entries"):
        op.create_table(
            "document_skill_entries",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column(
                "document_skill_revision_id",
                sa.String(length=36),
                sa.ForeignKey("document_skill_revisions.id"),
                nullable=False,
            ),
            sa.Column("entry_type", sa.String(length=50), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("normalized_text", sa.Text(), nullable=False),
            sa.Column("source_page", sa.Integer(), nullable=True),
            sa.Column("source_span", sa.String(length=100), nullable=True),
            sa.Column("confidence", sa.Float(), nullable=False),
            sa.Column("metadata_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    if not _table_exists("document_skill_usage_logs"):
        op.create_table(
            "document_skill_usage_logs",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("chat_message_id", sa.String(length=36), sa.ForeignKey("chat_messages.id"), nullable=False),
            sa.Column("document_id", sa.String(length=36), sa.ForeignKey("rag_documents.id"), nullable=False),
            sa.Column(
                "document_skill_revision_id",
                sa.String(length=36),
                sa.ForeignKey("document_skill_revisions.id"),
                nullable=False,
            ),
            sa.Column(
                "document_skill_entry_id",
                sa.String(length=36),
                sa.ForeignKey("document_skill_entries.id"),
                nullable=True,
            ),
            sa.Column("included_order", sa.Integer(), nullable=False),
            sa.Column("context_kind", sa.String(length=50), nullable=False),
            sa.Column("context_hash", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    if not _index_exists("document_skill_entries", "ix_document_skill_entries_revision"):
        op.create_index("ix_document_skill_entries_revision", "document_skill_entries", ["document_skill_revision_id"])

    if not _index_exists("document_skill_usage_logs", "ix_document_skill_usage_logs_message"):
        op.create_index("ix_document_skill_usage_logs_message", "document_skill_usage_logs", ["chat_message_id"])


def downgrade() -> None:
    pass
