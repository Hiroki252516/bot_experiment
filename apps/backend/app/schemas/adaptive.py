from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


RunState = Literal[
    "RUN_STARTED",
    "INITIAL_TEST_GENERATED",
    "INITIAL_TEST_SUBMITTED",
    "CYCLE_MATERIAL_GENERATED",
    "CYCLE_MATERIAL_READ",
    "CYCLE_TEST_GENERATED",
    "CYCLE_TEST_SUBMITTED",
    "FINAL_TEST_GENERATED",
    "FINAL_TEST_SUBMITTED",
    "RESULT_READY",
]


class DocumentSkillPayload(BaseModel):
    learning_objectives: list[str] = Field(default_factory=list)
    topic_map: list[dict] = Field(default_factory=list)
    concept_definitions: list[dict] = Field(default_factory=list)
    prerequisite_concepts: list[str] = Field(default_factory=list)
    examples: list[dict] = Field(default_factory=list)
    common_misconceptions: list[str] = Field(default_factory=list)
    difficulty_map: list[dict] = Field(default_factory=list)
    assessment_blueprint: list[dict] = Field(default_factory=list)
    canonical_explanations: list[dict] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    source_pdf_metadata: dict = Field(default_factory=dict)
    revision: int = 1


class AssessmentQuestion(BaseModel):
    question_id: str
    topic: str
    subtopic: str = ""
    difficulty: Literal["basic", "standard", "advanced"] = "basic"
    stem: str
    choices: list[str] = Field(min_length=2)
    correct_answer: str
    rubric: str = ""
    fingerprint: str = ""


class AssessmentPayload(BaseModel):
    title: str
    questions: list[AssessmentQuestion]
    blueprint: dict = Field(default_factory=dict)


class LearnerSkillPayload(BaseModel):
    overall_mastery: float = 0.0
    mastery_by_topic: dict[str, float] = Field(default_factory=dict)
    known_topics: list[str] = Field(default_factory=list)
    weak_topics: list[str] = Field(default_factory=list)
    common_mistakes: list[str] = Field(default_factory=list)
    misconception_hypotheses: list[str] = Field(default_factory=list)
    recommended_next_focus: list[str] = Field(default_factory=list)
    recommended_difficulty: str = "basic"
    generated_material_history_summary: list[str] = Field(default_factory=list)
    used_question_fingerprints: list[str] = Field(default_factory=list)
    evidence_from_attempts: list[dict] = Field(default_factory=list)
    revision: int = 1
    updated_at: datetime | None = None


class GeneratedMaterialPayload(BaseModel):
    title: str
    learning_goals: list[str] = Field(default_factory=list)
    body: str
    examples: list[str] = Field(default_factory=list)
    common_mistakes: list[str] = Field(default_factory=list)
    checkpoints: list[str] = Field(default_factory=list)
    target_topics: list[str] = Field(default_factory=list)
    difficulty: str = "basic"


class ResultSummaryPayload(BaseModel):
    ai_summary: str
    improved_topics: list[str] = Field(default_factory=list)
    remaining_weak_topics: list[str] = Field(default_factory=list)
    misconception_reduction: dict = Field(default_factory=dict)


class AdminDocumentUploadResponse(BaseModel):
    document_id: str
    status: str
    title: str
    created_at: datetime


class AdminDocumentResponse(BaseModel):
    document_id: str
    title: str
    description: str | None
    filename: str
    mime_type: str
    status: str
    created_at: datetime
    updated_at: datetime


class ExtractSkillResponse(BaseModel):
    document_id: str
    document_skill_revision_id: str
    status: str
    entry_count: int


class RunStartRequestV2(BaseModel):
    user_id: str
    document_id: str
    cycle_count: int = Field(default=10, ge=10, le=10)


class RunStartResponseV2(BaseModel):
    run_id: str
    state: RunState
    cycle_count: int


class RunStateResponse(BaseModel):
    run_id: str
    state: str
    cycle_count: int
    current_cycle_index: int
    next_action: str


class AssessmentGenerateResponse(BaseModel):
    assessment_id: str
    assessment_type: str
    cycle_index: int | None = None
    question_count: int
    state: str


class AnswerSubmission(BaseModel):
    question_id: str
    answer: str


class AssessmentSubmitRequestV2(BaseModel):
    answers: list[AnswerSubmission]
    submitted_at: datetime | None = None


class AssessmentSubmitResponseV2(BaseModel):
    attempt_id: str
    score: int
    max_score: int
    learner_skill_revision_id: str | None = None
    state: str
    next_cycle_index: int | None = None


class MaterialGenerateResponse(BaseModel):
    material_id: str
    cycle_index: int
    title: str
    state: str


class MaterialReadConfirmResponseV2(BaseModel):
    material_read_id: str
    read_duration_seconds: int
    state: str


class ResultResponse(BaseModel):
    run_id: str
    initial_score: int
    final_score: int
    gain_score: int
    gain_rate: float
    initial_accuracy: float
    final_accuracy: float
    accuracy_gain: float
    cycle_score_trend: list[dict]
    improved_topics: list[str]
    remaining_weak_topics: list[str]
    ai_summary: str


class ExportJobResponse(BaseModel):
    export_job_id: str
    status: str
    file_path: str | None = None
