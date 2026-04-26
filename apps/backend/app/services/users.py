from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import Skill, SkillRevision, User, utcnow


def create_user(
    session: Session,
    display_name: str | None = None,
    username: str | None = None,
    password_hash: str | None = None,
) -> tuple[User, SkillRevision]:
    settings = get_settings()
    user = User(username=username, password_hash=password_hash, display_name=display_name, last_seen_at=utcnow())
    session.add(user)
    session.flush()

    skill = Skill(user_id=user.id)
    session.add(skill)
    session.flush()

    revision = SkillRevision(
        skill_id=skill.id,
        revision_number=1,
        profile_json=settings.default_skill_profile,
        summary_rule="Initial default skill profile.",
        update_reason="bootstrap",
    )
    session.add(revision)
    session.flush()

    skill.active_revision_id = revision.id
    skill.updated_at = utcnow()
    session.commit()
    session.refresh(user)
    session.refresh(revision)
    return user, revision


def get_user_with_skill(session: Session, user_id: str) -> tuple[User | None, Skill | None, SkillRevision | None]:
    user = session.get(User, user_id)
    if not user:
        return None, None, None
    skill = session.scalar(select(Skill).where(Skill.user_id == user_id))
    revision = session.get(SkillRevision, skill.active_revision_id) if skill and skill.active_revision_id else None
    return user, skill, revision
