from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


GroupName = Literal["A", "B", "C"]
AssessmentType = Literal["pre_test", "mini_test", "post_test"]
MaterialSourceType = Literal["generated", "fixed"]


class RunStartRequest(BaseModel):
    user_id: str
    group: GroupName
    cycle_count: int = Field(default=3, ge=1, le=10)


class RunStartResponse(BaseModel):
    run_id: str
    user_id: str
    group: GroupName
    skills_enabled: bool
    cycle_count: int
    created_at: datetime


class RunFinishRequest(BaseModel):
    run_id: str


class RunFinishResponse(BaseModel):
    run_id: str
    finished_at: datetime


class MaterialNextRequest(BaseModel):
    run_id: str
    cycle_index: int = Field(ge=1, le=10)


class MaterialResponse(BaseModel):
    material_id: str
    run_id: str
    cycle_index: int
    group: GroupName
    source_type: MaterialSourceType
    content_text: str
    difficulty: str | None = None
    created_at: datetime


class MaterialReadConfirmRequest(BaseModel):
    run_id: str
    material_id: str
    presented_at: datetime
    read_confirmed_at: datetime


class MaterialReadConfirmResponse(BaseModel):
    material_read_id: str
    duration_seconds: int


class AssessmentStartRequest(BaseModel):
    run_id: str
    assessment_type: AssessmentType
    cycle_index: int | None = Field(default=None, ge=1, le=10)


class AssessmentStartResponse(BaseModel):
    assessment_attempt_id: str
    assessment_id: str
    assessment_type: AssessmentType
    cycle_index: int | None
    started_at: datetime


class McqAnswer(BaseModel):
    question_id: str
    choice_index: int = Field(ge=0)


class AssessmentSubmitRequest(BaseModel):
    assessment_attempt_id: str
    submitted_at: datetime
    answers: list[McqAnswer]


class PerQuestionCorrect(BaseModel):
    question_id: str
    is_correct: bool


class AssessmentSubmitResponse(BaseModel):
    assessment_attempt_id: str
    submitted_at: datetime
    duration_seconds: int
    score: int
    max_score: int
    per_question_correct: list[PerQuestionCorrect]


class MasteryEstimateRequest(BaseModel):
    run_id: str
    cycle_index: int = Field(ge=1, le=10)


class MasteryEstimateResponse(BaseModel):
    mastery_estimate_id: str
    run_id: str
    cycle_index: int
    estimate_json: dict
    created_at: datetime


class ChatAskRequest(BaseModel):
    run_id: str
    material_id: str
    question_text: str = Field(min_length=1, max_length=2000)


class ChatAskResponse(BaseModel):
    chat_turn_id: str
    answer_text: str
    created_at: datetime
