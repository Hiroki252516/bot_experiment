from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class UserCreateRequest(BaseModel):
    display_name: str | None = None


class UserResponse(BaseModel):
    user_id: str
    display_name: str | None
    created_at: datetime
    active_skill_revision_id: str | None


class SkillSummaryResponse(BaseModel):
    skill_id: str
    active_revision_id: str | None
    active_profile: dict
    revisions: list[dict]

