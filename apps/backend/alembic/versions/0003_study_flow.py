"""study flow tables (runs/materials/assessments)

Revision ID: 0003_study_flow
Revises: 0003_document_skills
Create Date: 2026-05-09 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_study_flow"
down_revision = "0003_document_skills"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "study_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("group", sa.String(length=1), nullable=False),
        sa.Column("skills_enabled", sa.Boolean(), nullable=False),
        sa.Column("cycle_count", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("provider_name", sa.String(length=100), nullable=True),
        sa.Column("model_name", sa.String(length=100), nullable=True),
        sa.Column("prompt_version", sa.String(length=100), nullable=True),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("top_p", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "study_materials",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("study_runs.id"), nullable=False),
        sa.Column("cycle_index", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("difficulty", sa.String(length=20), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_study_materials_run_cycle", "study_materials", ["run_id", "cycle_index"], unique=True)

    op.create_table(
        "study_material_reads",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("study_runs.id"), nullable=False),
        sa.Column("material_id", sa.String(length=36), sa.ForeignKey("study_materials.id"), nullable=False),
        sa.Column("presented_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "study_assessments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("study_runs.id"), nullable=False),
        sa.Column("assessment_type", sa.String(length=20), nullable=False),
        sa.Column("cycle_index", sa.Integer(), nullable=True),
        sa.Column("content_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "study_assessment_attempts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("study_runs.id"), nullable=False),
        sa.Column("assessment_id", sa.String(length=36), sa.ForeignKey("study_assessments.id"), nullable=False),
        sa.Column("assessment_type", sa.String(length=20), nullable=False),
        sa.Column("cycle_index", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("answers_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("max_score", sa.Integer(), nullable=True),
        sa.Column("result_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "study_mastery_estimates",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("study_runs.id"), nullable=False),
        sa.Column("cycle_index", sa.Integer(), nullable=False),
        sa.Column("estimate_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "study_chat_turns",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("study_runs.id"), nullable=False),
        sa.Column("material_id", sa.String(length=36), sa.ForeignKey("study_materials.id"), nullable=False),
        sa.Column("cycle_index", sa.Integer(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("study_chat_turns")
    op.drop_table("study_mastery_estimates")
    op.drop_table("study_assessment_attempts")
    op.drop_table("study_assessments")
    op.drop_table("study_material_reads")
    op.drop_index("ix_study_materials_run_cycle", table_name="study_materials")
    op.drop_table("study_materials")
    op.drop_table("study_runs")
