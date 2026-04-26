from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

import bcrypt
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.entities import AuthSession, SkillRevision, User, utcnow
from app.services.users import create_user, get_user_with_skill


class DuplicateUsernameError(ValueError):
    pass


class InvalidCredentialsError(ValueError):
    pass


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_auth_session(session: Session, user_id: str, settings: Settings) -> tuple[AuthSession, str]:
    raw_token = secrets.token_urlsafe(32)
    auth_session = AuthSession(
        user_id=user_id,
        session_token_hash=hash_session_token(raw_token),
        expires_at=utcnow() + timedelta(days=settings.auth_session_days),
    )
    session.add(auth_session)
    session.commit()
    session.refresh(auth_session)
    return auth_session, raw_token


def register_user(
    session: Session,
    *,
    username: str,
    password: str,
    display_name: str | None,
    settings: Settings,
) -> tuple[User, SkillRevision, str]:
    existing = session.scalar(select(User).where(User.username == username))
    if existing:
        raise DuplicateUsernameError("Username already exists")

    try:
        user, revision = create_user(
            session,
            display_name=display_name or username,
            username=username,
            password_hash=hash_password(password),
        )
    except IntegrityError as exc:
        session.rollback()
        raise DuplicateUsernameError("Username already exists") from exc

    _auth_session, raw_token = create_auth_session(session, user.id, settings)
    return user, revision, raw_token


def login_user(session: Session, *, username: str, password: str, settings: Settings) -> tuple[User, SkillRevision | None, str]:
    user = session.scalar(select(User).where(User.username == username))
    if not user or not user.password_hash or not verify_password(password, user.password_hash):
        raise InvalidCredentialsError("Invalid username or password")

    user.last_seen_at = utcnow()
    session.commit()
    _user, _skill, revision = get_user_with_skill(session, user.id)
    _auth_session, raw_token = create_auth_session(session, user.id, settings)
    return user, revision, raw_token


def get_user_for_session_token(session: Session, token: str) -> tuple[User | None, SkillRevision | None]:
    token_hash = hash_session_token(token)
    auth_session = session.scalar(select(AuthSession).where(AuthSession.session_token_hash == token_hash))
    if not auth_session:
        return None, None
    if auth_session.expires_at <= utcnow():
        session.delete(auth_session)
        session.commit()
        return None, None

    user, _skill, revision = get_user_with_skill(session, auth_session.user_id)
    return user, revision


def logout_session(session: Session, token: str) -> None:
    session.execute(delete(AuthSession).where(AuthSession.session_token_hash == hash_session_token(token)))
    session.commit()
