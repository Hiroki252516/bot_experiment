"""adaptive learning mvp tables

Revision ID: 0005_adaptive_learning_mvp
Revises: 0004_repair_doc_skills
Create Date: 2026-05-09 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005_adaptive_learning_mvp"
down_revision = "0004_repair_doc_skills"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    if _table_exists("experiment_runs"):
        for column in [
            sa.Column("document_id", sa.String(length=36), nullable=True),
            sa.Column("document_skill_revision_id", sa.String(length=36), nullable=True),
            sa.Column("state", sa.String(length=50), nullable=True),
            sa.Column("cycle_count", sa.Integer(), nullable=True),
            sa.Column("current_cycle_index", sa.Integer(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        ]:
            if not _column_exists("experiment_runs", column.name):
                op.add_column("experiment_runs", column)
        for column_name in ["chat_message_id", "condition_name", "skills_enabled", "candidate_count"]:
            if _column_exists("experiment_runs", column_name):
                try:
                    op.alter_column("experiment_runs", column_name, nullable=True)
                except Exception:
                    pass

    if not _table_exists("source_documents"):
        op.create_table(
            "source_documents",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("file_path", sa.Text(), nullable=False),
            sa.Column("filename", sa.String(length=255), nullable=False),
            sa.Column("mime_type", sa.String(length=255), nullable=False),
            sa.Column("sha256", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=50), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )

    if not _table_exists("adaptive_document_skill_revisions"):
        op.create_table(
            "adaptive_document_skill_revisions",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("document_id", sa.String(length=36), sa.ForeignKey("source_documents.id"), nullable=False),
            sa.Column("revision", sa.Integer(), nullable=False),
            sa.Column("skill_json", sa.JSON(), nullable=False),
            sa.Column("extraction_prompt_version", sa.String(length=100), nullable=False),
            sa.Column("provider", sa.String(length=100), nullable=False),
            sa.Column("model", sa.String(length=100), nullable=False),
            sa.Column("schema_version", sa.String(length=100), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    if not _table_exists("adaptive_document_skill_entries"):
        op.create_table(
            "adaptive_document_skill_entries",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column(
                "document_skill_revision_id",
                sa.String(length=36),
                sa.ForeignKey("adaptive_document_skill_revisions.id"),
                nullable=False,
            ),
            sa.Column("entry_type", sa.String(length=50), nullable=False),
            sa.Column("topic_key", sa.String(length=255), nullable=True),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("content_json", sa.JSON(), nullable=False),
            sa.Column("difficulty", sa.String(length=50), nullable=True),
            sa.Column("order_index", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    if not _table_exists("generated_assessments"):
        op.create_table(
            "generated_assessments",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("run_id", sa.String(length=36), sa.ForeignKey("experiment_runs.id"), nullable=False),
            sa.Column("assessment_type", sa.String(length=20), nullable=False),
            sa.Column("cycle_index", sa.Integer(), nullable=True),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("questions_json", sa.JSON(), nullable=False),
            sa.Column("blueprint_json", sa.JSON(), nullable=False),
            sa.Column("question_fingerprints_json", sa.JSON(), nullable=False),
            sa.Column("provider", sa.String(length=100), nullable=False),
            sa.Column("model", sa.String(length=100), nullable=False),
            sa.Column("prompt_version", sa.String(length=100), nullable=False),
            sa.Column("temperature", sa.Float(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    if not _table_exists("assessment_items"):
        op.create_table(
            "assessment_items",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("assessment_id", sa.String(length=36), sa.ForeignKey("generated_assessments.id"), nullable=False),
            sa.Column("question_id", sa.String(length=100), nullable=False),
            sa.Column("item_index", sa.Integer(), nullable=False),
            sa.Column("topic", sa.String(length=255), nullable=False),
            sa.Column("subtopic", sa.String(length=255), nullable=True),
            sa.Column("difficulty", sa.String(length=50), nullable=False),
            sa.Column("stem", sa.Text(), nullable=False),
            sa.Column("choices_json", sa.JSON(), nullable=False),
            sa.Column("correct_answer", sa.Text(), nullable=False),
            sa.Column("rubric", sa.Text(), nullable=False),
            sa.Column("fingerprint", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    if not _table_exists("assessment_attempts"):
        op.create_table(
            "assessment_attempts",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("assessment_id", sa.String(length=36), sa.ForeignKey("generated_assessments.id"), nullable=False),
            sa.Column("run_id", sa.String(length=36), sa.ForeignKey("experiment_runs.id"), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("duration_seconds", sa.Integer(), nullable=True),
            sa.Column("answers_json", sa.JSON(), nullable=False),
            sa.Column("score", sa.Integer(), nullable=True),
            sa.Column("max_score", sa.Integer(), nullable=True),
            sa.Column("per_question_correct_json", sa.JSON(), nullable=False),
            sa.Column("analysis_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    if not _table_exists("generated_materials"):
        op.create_table(
            "generated_materials",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("run_id", sa.String(length=36), sa.ForeignKey("experiment_runs.id"), nullable=False),
            sa.Column("cycle_index", sa.Integer(), nullable=False),
            sa.Column("learner_skill_revision_id", sa.String(length=36), nullable=True),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("content_markdown", sa.Text(), nullable=False),
            sa.Column("focus_topics_json", sa.JSON(), nullable=False),
            sa.Column("provider", sa.String(length=100), nullable=False),
            sa.Column("model", sa.String(length=100), nullable=False),
            sa.Column("prompt_version", sa.String(length=100), nullable=False),
            sa.Column("temperature", sa.Float(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    if not _table_exists("material_reads"):
        op.create_table(
            "material_reads",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("material_id", sa.String(length=36), sa.ForeignKey("generated_materials.id"), nullable=False),
            sa.Column("run_id", sa.String(length=36), sa.ForeignKey("experiment_runs.id"), nullable=False),
            sa.Column("cycle_index", sa.Integer(), nullable=False),
            sa.Column("presented_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("read_confirmed_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("read_duration_seconds", sa.Integer(), nullable=False),
        )

    if not _table_exists("learner_skill_revisions"):
        op.create_table(
            "learner_skill_revisions",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("run_id", sa.String(length=36), sa.ForeignKey("experiment_runs.id"), nullable=False),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("revision", sa.Integer(), nullable=False),
            sa.Column("source_attempt_id", sa.String(length=36), sa.ForeignKey("assessment_attempts.id"), nullable=True),
            sa.Column("skill_json", sa.JSON(), nullable=False),
            sa.Column("update_reason", sa.Text(), nullable=False),
            sa.Column("provider", sa.String(length=100), nullable=False),
            sa.Column("model", sa.String(length=100), nullable=False),
            sa.Column("prompt_version", sa.String(length=100), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    if not _table_exists("generation_logs"):
        op.create_table(
            "generation_logs",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("run_id", sa.String(length=36), sa.ForeignKey("experiment_runs.id"), nullable=True),
            sa.Column("generation_type", sa.String(length=100), nullable=False),
            sa.Column("input_summary_json", sa.JSON(), nullable=False),
            sa.Column("output_json", sa.JSON(), nullable=False),
            sa.Column("validation_status", sa.String(length=50), nullable=False),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("provider", sa.String(length=100), nullable=False),
            sa.Column("model", sa.String(length=100), nullable=False),
            sa.Column("prompt_version", sa.String(length=100), nullable=False),
            sa.Column("temperature", sa.Float(), nullable=False),
            sa.Column("input_schema_version", sa.String(length=100), nullable=False),
            sa.Column("output_schema_version", sa.String(length=100), nullable=False),
            sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    if not _table_exists("result_summaries"):
        op.create_table(
            "result_summaries",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("run_id", sa.String(length=36), sa.ForeignKey("experiment_runs.id"), nullable=False, unique=True),
            sa.Column("initial_score", sa.Integer(), nullable=False),
            sa.Column("final_score", sa.Integer(), nullable=False),
            sa.Column("gain_score", sa.Integer(), nullable=False),
            sa.Column("gain_rate", sa.Float(), nullable=False),
            sa.Column("initial_accuracy", sa.Float(), nullable=False),
            sa.Column("final_accuracy", sa.Float(), nullable=False),
            sa.Column("accuracy_gain", sa.Float(), nullable=False),
            sa.Column("cycle_score_trend", sa.JSON(), nullable=False),
            sa.Column("topic_mastery_before_after", sa.JSON(), nullable=False),
            sa.Column("improved_topics", sa.JSON(), nullable=False),
            sa.Column("remaining_weak_topics", sa.JSON(), nullable=False),
            sa.Column("misconception_reduction", sa.JSON(), nullable=False),
            sa.Column("material_read_duration_summary", sa.JSON(), nullable=False),
            sa.Column("test_duration_summary", sa.JSON(), nullable=False),
            sa.Column("ai_summary", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    if not _table_exists("export_jobs"):
        op.create_table(
            "export_jobs",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("run_id", sa.String(length=36), sa.ForeignKey("experiment_runs.id"), nullable=True),
            sa.Column("status", sa.String(length=50), nullable=False),
            sa.Column("file_path", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    op.drop_table("export_jobs")
    op.drop_table("result_summaries")
    op.drop_table("generation_logs")
    op.drop_table("learner_skill_revisions")
    op.drop_table("material_reads")
    op.drop_table("generated_materials")
    op.drop_table("assessment_attempts")
    op.drop_table("assessment_items")
    op.drop_table("generated_assessments")
    op.drop_table("adaptive_document_skill_entries")
    op.drop_table("adaptive_document_skill_revisions")
    op.drop_table("source_documents")
