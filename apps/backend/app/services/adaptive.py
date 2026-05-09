from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile
from pypdf import PdfReader
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.llm.providers import get_generation_provider
from app.models.entities import (
    AdaptiveDocumentSkillEntry,
    AdaptiveDocumentSkillRevision,
    AssessmentAttempt,
    AssessmentItem,
    ExportJob,
    GeneratedAssessment,
    GeneratedMaterial,
    GenerationLog,
    LearnerSkillRevision,
    MaterialRead,
    ResultSummary,
    SourceDocument,
    ExperimentRun,
    User,
    utcnow,
)
from app.schemas.adaptive import (
    AssessmentPayload,
    DocumentSkillPayload,
    GeneratedMaterialPayload,
    LearnerSkillPayload,
    ResultSummaryPayload,
)


INITIAL_QUESTION_COUNT = 20
CYCLE_QUESTION_COUNT = 10
FINAL_QUESTION_COUNT = 20
CYCLE_COUNT = 10


def save_source_document(session: Session, file: UploadFile, title: str, description: str | None) -> SourceDocument:
    settings = get_settings()
    content = file.file.read()
    digest = hashlib.sha256(content).hexdigest()
    filename = file.filename or "uploaded.pdf"
    storage_path = settings.upload_dir / f"{utcnow().timestamp()}_{filename}"
    storage_path.write_bytes(content)
    document = SourceDocument(
        title=title or filename,
        description=description,
        file_path=str(storage_path),
        filename=filename,
        mime_type=file.content_type or "application/pdf",
        sha256=digest,
        status="uploaded",
        updated_at=utcnow(),
    )
    session.add(document)
    session.commit()
    session.refresh(document)
    return document


def list_source_documents(session: Session) -> list[SourceDocument]:
    return list(session.scalars(select(SourceDocument).order_by(SourceDocument.created_at.desc())))


def delete_source_document(session: Session, document_id: str) -> bool:
    document = session.get(SourceDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    run_exists = session.scalar(select(ExperimentRun.id).where(ExperimentRun.document_id == document.id).limit(1))
    if run_exists:
        document.status = "deleted"
        document.updated_at = utcnow()
        session.commit()
        return False

    revision_ids = list(
        session.scalars(
            select(AdaptiveDocumentSkillRevision.id).where(AdaptiveDocumentSkillRevision.document_id == document.id)
        )
    )
    if revision_ids:
        session.execute(
            delete(AdaptiveDocumentSkillEntry).where(
                AdaptiveDocumentSkillEntry.document_skill_revision_id.in_(revision_ids)
            )
        )
        session.execute(
            delete(AdaptiveDocumentSkillRevision).where(AdaptiveDocumentSkillRevision.id.in_(revision_ids))
        )
    session.delete(document)
    session.commit()

    try:
        Path(document.file_path).unlink(missing_ok=True)
    except OSError:
        # DB delete is more important for keeping the UI usable; stale files can be cleaned manually.
        pass
    return True


def extract_document_skill(session: Session, document_id: str) -> tuple[SourceDocument, AdaptiveDocumentSkillRevision, int]:
    document = session.get(SourceDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    document.status = "processing"
    document.updated_at = utcnow()
    session.commit()

    source_text = _extract_text(Path(document.file_path), document.mime_type)
    if len(source_text.strip()) < 200:
        document.status = "failed"
        document.updated_at = utcnow()
        session.commit()
        raise HTTPException(
            status_code=422,
            detail=(
                "PDFから十分なテキストを抽出できませんでした。OCR済みPDF、またはテキスト抽出可能なPDFをアップロードしてください。"
            ),
        )
    provider = get_generation_provider(get_settings())
    metadata = {
        "document_id": document.id,
        "title": document.title,
        "filename": document.filename,
        "mime_type": document.mime_type,
        "sha256": document.sha256,
    }
    try:
        skill, provider_meta = provider.extract_document_skill(metadata, source_text)
        _validate_document_skill_is_grounded(skill, source_text)
        revision_number = _next_document_revision(session, document.id)
        skill.revision = revision_number
        skill.source_pdf_metadata = metadata
        revision = AdaptiveDocumentSkillRevision(
            document_id=document.id,
            revision=revision_number,
            skill_json=skill.model_dump(mode="json"),
            extraction_prompt_version=provider_meta.prompt_version,
            provider=provider_meta.provider_name,
            model=provider_meta.model_name,
            schema_version="document-agent-skill-v1",
        )
        session.add(revision)
        session.flush()
        entry_count = _insert_document_skill_entries(session, revision.id, skill)
        document.status = "ready"
        document.updated_at = utcnow()
        _log_generation(
            session,
            run_id=None,
            generation_type="document_skill_extraction",
            input_summary={"document_id": document.id, "text_chars": len(source_text)},
            output=skill.model_dump(mode="json"),
            validation_status="valid",
            provider_meta=provider_meta,
        )
        session.commit()
        return document, revision, entry_count
    except Exception as exc:
        session.rollback()
        failed = session.get(SourceDocument, document_id)
        if failed:
            failed.status = "failed"
            failed.updated_at = utcnow()
            session.commit()
        raise HTTPException(status_code=502, detail=f"Document Skill extraction failed: {exc}") from exc


def start_run(session: Session, user_id: str, document_id: str, cycle_count: int = CYCLE_COUNT) -> ExperimentRun:
    if cycle_count != CYCLE_COUNT:
        raise HTTPException(status_code=400, detail="cycle_count must be 10 for MVP")
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    document = session.get(SourceDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    if document.status != "ready":
        raise HTTPException(status_code=409, detail="Document Agent Skill is not ready")
    doc_revision = _latest_document_skill_revision(session, document_id)
    if not doc_revision:
        raise HTTPException(status_code=409, detail="Document Agent Skill revision is missing")

    run = ExperimentRun(
        user_id=user_id,
        document_id=document_id,
        document_skill_revision_id=doc_revision.id,
        state="RUN_STARTED",
        cycle_count=CYCLE_COUNT,
        current_cycle_index=0,
        started_at=utcnow(),
        created_at=utcnow(),
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def get_run_state(session: Session, run_id: str) -> dict[str, Any]:
    run = _require_run(session, run_id)
    return {
        "run_id": run.id,
        "state": run.state,
        "cycle_count": run.cycle_count,
        "current_cycle_index": run.current_cycle_index,
        "next_action": _next_action(run),
    }


def generate_initial_test(session: Session, run_id: str) -> GeneratedAssessment:
    run = _require_state(session, run_id, {"RUN_STARTED"})
    document_skill = _document_skill_json(session, run)
    assessment, meta = get_generation_provider(get_settings()).generate_initial_test(
        document_skill=document_skill,
        question_count=INITIAL_QUESTION_COUNT,
        used_fingerprints=[],
    )
    generated = _save_assessment(session, run, "initial", None, assessment, meta)
    run.state = "INITIAL_TEST_GENERATED"
    _log_generation(session, run.id, "initial_test", {"question_count": INITIAL_QUESTION_COUNT}, assessment.model_dump(mode="json"), "valid", meta)
    session.commit()
    return generated


def submit_initial_test(session: Session, run_id: str, answers: list[dict], submitted_at: datetime | None = None) -> tuple[AssessmentAttempt, LearnerSkillRevision]:
    run = _require_state(session, run_id, {"INITIAL_TEST_GENERATED"})
    assessment = _latest_assessment(session, run.id, "initial", None)
    attempt = _score_and_save_attempt(session, run, assessment, answers, submitted_at)
    document_skill = _document_skill_json(session, run)
    provider = get_generation_provider(get_settings())
    learner, meta = provider.analyze_attempt_and_create_learner_skill(
        document_skill=document_skill,
        assessment=assessment.questions_json,
        attempt=_attempt_payload(attempt),
        revision=1,
    )
    revision = _save_learner_skill_revision(session, run, attempt, learner, "initial_test_analysis", meta)
    run.state = "INITIAL_TEST_SUBMITTED"
    run.current_cycle_index = 1
    _log_generation(session, run.id, "learner_skill_initial", {"attempt_id": attempt.id}, learner.model_dump(mode="json"), "valid", meta)
    session.commit()
    return attempt, revision


def generate_cycle_material(session: Session, run_id: str, cycle_index: int) -> GeneratedMaterial:
    run = _require_run(session, run_id)
    _validate_cycle(run, cycle_index)
    allowed = {"INITIAL_TEST_SUBMITTED"} if cycle_index == 1 else {"CYCLE_TEST_SUBMITTED"}
    if run.state not in allowed or run.current_cycle_index != cycle_index:
        raise HTTPException(status_code=409, detail="Cycle material cannot be generated in current state")
    document_skill = _document_skill_json(session, run)
    learner_revision = _latest_learner_skill_revision(session, run.id)
    if not learner_revision:
        raise HTTPException(status_code=409, detail="Learner Agent Skill is missing")
    material, meta = get_generation_provider(get_settings()).generate_learning_material(
        document_skill=document_skill,
        learner_skill=learner_revision.skill_json,
        cycle_index=cycle_index,
    )
    saved = GeneratedMaterial(
        run_id=run.id,
        cycle_index=cycle_index,
        learner_skill_revision_id=learner_revision.id,
        title=material.title,
        content_markdown=_material_markdown(material),
        focus_topics_json=material.target_topics,
        provider=meta.provider_name,
        model=meta.model_name,
        prompt_version=meta.prompt_version,
        temperature=meta.temperature,
    )
    session.add(saved)
    run.state = "CYCLE_MATERIAL_GENERATED"
    _log_generation(session, run.id, "learning_material", {"cycle_index": cycle_index}, material.model_dump(mode="json"), "valid", meta)
    session.commit()
    session.refresh(saved)
    return saved


def confirm_material_read(session: Session, run_id: str, cycle_index: int, presented_at: datetime | None = None) -> MaterialRead:
    run = _require_state(session, run_id, {"CYCLE_MATERIAL_GENERATED"})
    _validate_cycle(run, cycle_index)
    material = _latest_material(session, run.id, cycle_index)
    now = utcnow()
    start = presented_at or material.created_at
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    duration = max(0, int((now - start).total_seconds()))
    read = MaterialRead(
        material_id=material.id,
        run_id=run.id,
        cycle_index=cycle_index,
        presented_at=start,
        read_confirmed_at=now,
        read_duration_seconds=duration,
    )
    session.add(read)
    run.state = "CYCLE_MATERIAL_READ"
    session.commit()
    session.refresh(read)
    return read


def generate_cycle_test(session: Session, run_id: str, cycle_index: int) -> GeneratedAssessment:
    run = _require_state(session, run_id, {"CYCLE_MATERIAL_READ"})
    _validate_cycle(run, cycle_index)
    document_skill = _document_skill_json(session, run)
    learner_revision = _latest_learner_skill_revision(session, run.id)
    if not learner_revision:
        raise HTTPException(status_code=409, detail="Learner Agent Skill is missing")
    used = _used_fingerprints(session, run.id)
    assessment, meta = get_generation_provider(get_settings()).generate_cycle_test(
        document_skill=document_skill,
        learner_skill=learner_revision.skill_json,
        cycle_index=cycle_index,
        question_count=CYCLE_QUESTION_COUNT,
        used_fingerprints=used,
    )
    assessment = _ensure_unique_fingerprints(assessment, used, f"cycle{cycle_index}")
    generated = _save_assessment(session, run, "cycle", cycle_index, assessment, meta)
    run.state = "CYCLE_TEST_GENERATED"
    _log_generation(session, run.id, "cycle_test", {"cycle_index": cycle_index, "question_count": CYCLE_QUESTION_COUNT}, assessment.model_dump(mode="json"), "valid", meta)
    session.commit()
    return generated


def submit_cycle_test(session: Session, run_id: str, cycle_index: int, answers: list[dict], submitted_at: datetime | None = None) -> tuple[AssessmentAttempt, LearnerSkillRevision]:
    run = _require_state(session, run_id, {"CYCLE_TEST_GENERATED"})
    _validate_cycle(run, cycle_index)
    assessment = _latest_assessment(session, run.id, "cycle", cycle_index)
    attempt = _score_and_save_attempt(session, run, assessment, answers, submitted_at)
    previous = _latest_learner_skill_revision(session, run.id)
    if not previous:
        raise HTTPException(status_code=409, detail="Learner Agent Skill is missing")
    provider = get_generation_provider(get_settings())
    learner, meta = provider.update_learner_skill(
        document_skill=_document_skill_json(session, run),
        previous_skill=previous.skill_json,
        assessment=assessment.questions_json,
        attempt=_attempt_payload(attempt),
        revision=previous.revision + 1,
    )
    revision = _save_learner_skill_revision(session, run, attempt, learner, f"cycle_{cycle_index}_analysis", meta)
    run.state = "CYCLE_TEST_SUBMITTED"
    if cycle_index < run.cycle_count:
        run.current_cycle_index = cycle_index + 1
    _log_generation(session, run.id, "learner_skill_update", {"cycle_index": cycle_index}, learner.model_dump(mode="json"), "valid", meta)
    session.commit()
    return attempt, revision


def generate_final_test(session: Session, run_id: str) -> GeneratedAssessment:
    run = _require_state(session, run_id, {"CYCLE_TEST_SUBMITTED"})
    if run.current_cycle_index != run.cycle_count:
        raise HTTPException(status_code=409, detail="Final test requires cycle 10 submission")
    used = _used_fingerprints(session, run.id)
    assessment, meta = get_generation_provider(get_settings()).generate_final_test(
        document_skill=_document_skill_json(session, run),
        question_count=FINAL_QUESTION_COUNT,
        used_fingerprints=used,
    )
    assessment = _ensure_unique_fingerprints(assessment, used, "final")
    generated = _save_assessment(session, run, "final", None, assessment, meta)
    run.state = "FINAL_TEST_GENERATED"
    _log_generation(session, run.id, "final_test", {"question_count": FINAL_QUESTION_COUNT}, assessment.model_dump(mode="json"), "valid", meta)
    session.commit()
    return generated


def submit_final_test(session: Session, run_id: str, answers: list[dict], submitted_at: datetime | None = None) -> tuple[AssessmentAttempt, ResultSummary]:
    run = _require_state(session, run_id, {"FINAL_TEST_GENERATED"})
    assessment = _latest_assessment(session, run.id, "final", None)
    attempt = _score_and_save_attempt(session, run, assessment, answers, submitted_at)
    summary = _create_result_summary(session, run)
    run.state = "RESULT_READY"
    run.finished_at = utcnow()
    session.commit()
    return attempt, summary


def get_results(session: Session, run_id: str) -> ResultSummary:
    run = _require_run(session, run_id)
    summary = session.scalar(select(ResultSummary).where(ResultSummary.run_id == run.id))
    if not summary:
        raise HTTPException(status_code=404, detail="Result summary not found")
    return summary


def export_run_zip(session: Session, run_id: str | None = None) -> ExportJob:
    settings = get_settings()
    job = ExportJob(run_id=run_id, status="running")
    session.add(job)
    session.flush()
    path = settings.export_dir / f"adaptive_export_{job.id}.zip"
    payloads = _build_csv_payloads(session, run_id)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in payloads.items():
            archive.writestr(name, content)
    job.status = "completed"
    job.file_path = str(path)
    job.completed_at = utcnow()
    session.commit()
    session.refresh(job)
    return job


def get_export_job(session: Session, export_job_id: str) -> ExportJob:
    job = session.get(ExportJob, export_job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Export job not found")
    return job


def _extract_text(path: Path, mime_type: str) -> str:
    if mime_type == "application/pdf" or path.suffix.lower() == ".pdf":
        reader = PdfReader(str(path))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages).strip()
    return path.read_text(encoding="utf-8", errors="ignore")


def _validate_document_skill_is_grounded(skill: DocumentSkillPayload, source_text: str) -> None:
    serialized = json.dumps(skill.model_dump(mode="json"), ensure_ascii=False)
    forbidden_markers = [
        "PDFの内容から抽出された",
        "主要な用語1",
        "主要な用語2",
        "概念X",
        "概念Y",
        "Term A",
        "Term B",
        "ここに",
    ]
    if any(marker in serialized for marker in forbidden_markers):
        raise ValueError("Document Agent Skill contains placeholder/generic content")
    source_compact = source_text.replace(" ", "")
    grounded_terms = ["仮定法", "過去形", "過去完了", "would", "could", "might", "If"]
    if any(term in source_compact or term in source_text for term in grounded_terms):
        if "仮定" not in serialized and "would" not in serialized and "If" not in serialized:
            raise ValueError("Document Agent Skill is not grounded in the uploaded grammar material")


def _next_document_revision(session: Session, document_id: str) -> int:
    latest = session.scalar(
        select(AdaptiveDocumentSkillRevision.revision)
        .where(AdaptiveDocumentSkillRevision.document_id == document_id)
        .order_by(AdaptiveDocumentSkillRevision.revision.desc())
        .limit(1)
    )
    return (latest or 0) + 1


def _latest_document_skill_revision(session: Session, document_id: str) -> AdaptiveDocumentSkillRevision | None:
    return session.scalar(
        select(AdaptiveDocumentSkillRevision)
        .where(AdaptiveDocumentSkillRevision.document_id == document_id)
        .order_by(AdaptiveDocumentSkillRevision.revision.desc())
        .limit(1)
    )


def _insert_document_skill_entries(session: Session, revision_id: str, skill: DocumentSkillPayload) -> int:
    entries: list[tuple[str, str | None, str, dict, str | None]] = []
    for index, item in enumerate(skill.topic_map):
        entries.append(("topic", str(item.get("topic_key") or f"topic_{index + 1}"), str(item.get("title") or item), item, None))
    for item in skill.concept_definitions:
        entries.append(("concept_definition", str(item.get("topic_key") or item.get("term") or ""), str(item.get("term") or "concept"), item, None))
    for item in skill.examples:
        entries.append(("example", str(item.get("topic_key") or ""), str(item.get("title") or "example"), item, None))
    for item in skill.assessment_blueprint:
        entries.append(("assessment_blueprint", str(item.get("topic_key") or ""), str(item.get("title") or "blueprint"), item, str(item.get("difficulty") or "")))
    if not entries:
        entries.append(("summary", None, "Document Skill", skill.model_dump(mode="json"), None))
    for order_index, (entry_type, topic_key, title, content, difficulty) in enumerate(entries):
        session.add(
            AdaptiveDocumentSkillEntry(
                document_skill_revision_id=revision_id,
                entry_type=entry_type,
                topic_key=topic_key,
                title=title[:255],
                content_json=content,
                difficulty=difficulty,
                order_index=order_index,
            )
        )
    return len(entries)


def _require_run(session: Session, run_id: str) -> ExperimentRun:
    run = session.get(ExperimentRun, run_id)
    if not run or not run.document_id:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


def _require_state(session: Session, run_id: str, states: set[str]) -> ExperimentRun:
    run = _require_run(session, run_id)
    if run.state not in states:
        raise HTTPException(status_code=409, detail=f"Invalid state: {run.state}")
    return run


def _validate_cycle(run: ExperimentRun, cycle_index: int) -> None:
    if cycle_index < 1 or cycle_index > run.cycle_count:
        raise HTTPException(status_code=400, detail="cycle_index out of range")
    if run.current_cycle_index != cycle_index:
        raise HTTPException(status_code=409, detail="cycle_index does not match current run state")


def _document_skill_json(session: Session, run: ExperimentRun) -> dict:
    if not run.document_skill_revision_id:
        raise HTTPException(status_code=409, detail="Run has no Document Agent Skill revision")
    revision = session.get(AdaptiveDocumentSkillRevision, run.document_skill_revision_id)
    if not revision:
        raise HTTPException(status_code=409, detail="Document Agent Skill revision not found")
    return revision.skill_json


def _save_assessment(session: Session, run: ExperimentRun, assessment_type: str, cycle_index: int | None, payload: AssessmentPayload, meta) -> GeneratedAssessment:
    payload = _ensure_question_fingerprints(payload, f"{assessment_type}{cycle_index or ''}")
    generated = GeneratedAssessment(
        run_id=run.id,
        assessment_type=assessment_type,
        cycle_index=cycle_index,
        title=payload.title,
        questions_json=payload.model_dump(mode="json"),
        blueprint_json=payload.blueprint,
        question_fingerprints_json=[q.fingerprint for q in payload.questions],
        provider=meta.provider_name,
        model=meta.model_name,
        prompt_version=meta.prompt_version,
        temperature=meta.temperature,
    )
    session.add(generated)
    session.flush()
    for index, question in enumerate(payload.questions, start=1):
        session.add(
            AssessmentItem(
                assessment_id=generated.id,
                question_id=question.question_id,
                item_index=index,
                topic=question.topic,
                subtopic=question.subtopic,
                difficulty=question.difficulty,
                stem=question.stem,
                choices_json=question.choices,
                correct_answer=question.correct_answer,
                rubric=question.rubric,
                fingerprint=question.fingerprint,
            )
        )
    return generated


def _latest_assessment(session: Session, run_id: str, assessment_type: str, cycle_index: int | None) -> GeneratedAssessment:
    stmt = select(GeneratedAssessment).where(
        GeneratedAssessment.run_id == run_id,
        GeneratedAssessment.assessment_type == assessment_type,
    )
    if cycle_index is None:
        stmt = stmt.where(GeneratedAssessment.cycle_index.is_(None))
    else:
        stmt = stmt.where(GeneratedAssessment.cycle_index == cycle_index)
    assessment = session.scalar(stmt.order_by(GeneratedAssessment.created_at.desc()).limit(1))
    if not assessment:
        raise HTTPException(status_code=409, detail="Assessment not generated")
    return assessment


def _score_and_save_attempt(session: Session, run: ExperimentRun, assessment: GeneratedAssessment, answers: list[dict], submitted_at: datetime | None) -> AssessmentAttempt:
    now = submitted_at or utcnow()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    started_at = assessment.created_at
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    questions = {q["question_id"]: q for q in assessment.questions_json.get("questions", [])}
    answer_map = {item["question_id"]: str(item["answer"]) for item in answers}
    per_question = []
    score = 0
    for qid, question in questions.items():
        expected = str(question.get("correct_answer", "")).strip()
        actual = str(answer_map.get(qid, "")).strip()
        is_correct = actual == expected
        if is_correct:
            score += 1
        per_question.append(
            {
                "question_id": qid,
                "topic": question.get("topic", ""),
                "is_correct": is_correct,
                "answer": actual,
                "correct_answer": expected,
            }
        )
    attempt = AssessmentAttempt(
        assessment_id=assessment.id,
        run_id=run.id,
        started_at=started_at,
        submitted_at=now,
        duration_seconds=max(0, int((now - started_at).total_seconds())),
        answers_json={"answers": answers},
        score=score,
        max_score=len(questions),
        per_question_correct_json=per_question,
        analysis_json=_basic_analysis(per_question),
    )
    session.add(attempt)
    session.flush()
    return attempt


def _basic_analysis(per_question: list[dict]) -> dict:
    by_topic: dict[str, list[bool]] = {}
    for row in per_question:
        by_topic.setdefault(row.get("topic") or "unknown", []).append(bool(row.get("is_correct")))
    return {
        "topic_accuracy": {topic: sum(values) / max(1, len(values)) for topic, values in by_topic.items()},
        "weak_topics": [topic for topic, values in by_topic.items() if (sum(values) / max(1, len(values))) < 0.7],
    }


def _attempt_payload(attempt: AssessmentAttempt) -> dict:
    return {
        "attempt_id": attempt.id,
        "score": attempt.score,
        "max_score": attempt.max_score,
        "per_question_correct": attempt.per_question_correct_json,
        "analysis": attempt.analysis_json,
    }


def _save_learner_skill_revision(session: Session, run: ExperimentRun, attempt: AssessmentAttempt, learner: LearnerSkillPayload, reason: str, meta) -> LearnerSkillRevision:
    learner.updated_at = learner.updated_at or utcnow()
    revision = LearnerSkillRevision(
        run_id=run.id,
        user_id=run.user_id,
        revision=learner.revision,
        source_attempt_id=attempt.id,
        skill_json=learner.model_dump(mode="json"),
        update_reason=reason,
        provider=meta.provider_name,
        model=meta.model_name,
        prompt_version=meta.prompt_version,
    )
    session.add(revision)
    session.flush()
    return revision


def _latest_learner_skill_revision(session: Session, run_id: str) -> LearnerSkillRevision | None:
    return session.scalar(
        select(LearnerSkillRevision)
        .where(LearnerSkillRevision.run_id == run_id)
        .order_by(LearnerSkillRevision.revision.desc())
        .limit(1)
    )


def _latest_material(session: Session, run_id: str, cycle_index: int) -> GeneratedMaterial:
    material = session.scalar(
        select(GeneratedMaterial)
        .where(GeneratedMaterial.run_id == run_id, GeneratedMaterial.cycle_index == cycle_index)
        .order_by(GeneratedMaterial.created_at.desc())
        .limit(1)
    )
    if not material:
        raise HTTPException(status_code=409, detail="Material not generated")
    return material


def _used_fingerprints(session: Session, run_id: str) -> list[str]:
    assessments = session.scalars(select(GeneratedAssessment).where(GeneratedAssessment.run_id == run_id))
    used: list[str] = []
    for assessment in assessments:
        used.extend([str(item) for item in assessment.question_fingerprints_json])
    latest = _latest_learner_skill_revision(session, run_id)
    if latest:
        used.extend([str(item) for item in latest.skill_json.get("used_question_fingerprints", [])])
    return list(dict.fromkeys([item for item in used if item]))


def _ensure_question_fingerprints(payload: AssessmentPayload, prefix: str) -> AssessmentPayload:
    data = payload.model_dump(mode="json")
    for index, question in enumerate(data["questions"], start=1):
        if not question.get("fingerprint"):
            raw = f"{prefix}:{question.get('topic')}:{question.get('stem')}:{index}"
            question["fingerprint"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return AssessmentPayload.model_validate(data)


def _ensure_unique_fingerprints(payload: AssessmentPayload, used: list[str], prefix: str) -> AssessmentPayload:
    data = _ensure_question_fingerprints(payload, prefix).model_dump(mode="json")
    seen = set(used)
    for index, question in enumerate(data["questions"], start=1):
        fingerprint = str(question["fingerprint"])
        if fingerprint in seen:
            raw = f"{prefix}:{index}:{question.get('stem')}:{utcnow().timestamp()}"
            fingerprint = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
            question["fingerprint"] = fingerprint
        seen.add(fingerprint)
    return AssessmentPayload.model_validate(data)


def _material_markdown(material: GeneratedMaterialPayload) -> str:
    sections = [
        f"# {material.title}",
        "## 学習目標\n" + "\n".join(f"- {item}" for item in material.learning_goals),
        material.body,
        "## 例\n" + "\n".join(f"- {item}" for item in material.examples),
        "## よくある誤り\n" + "\n".join(f"- {item}" for item in material.common_mistakes),
        "## 確認ポイント\n" + "\n".join(f"- {item}" for item in material.checkpoints),
    ]
    return "\n\n".join(sections)


def _create_result_summary(session: Session, run: ExperimentRun) -> ResultSummary:
    initial = _latest_attempt_for(session, run.id, "initial", None)
    final = _latest_attempt_for(session, run.id, "final", None)
    cycle_attempts = [
        _latest_attempt_for(session, run.id, "cycle", cycle_index)
        for cycle_index in range(1, run.cycle_count + 1)
    ]
    initial_accuracy = (initial.score or 0) / max(1, initial.max_score or 1)
    final_accuracy = (final.score or 0) / max(1, final.max_score or 1)
    latest_skill = _latest_learner_skill_revision(session, run.id)
    score_summary = {
        "initial_score": initial.score or 0,
        "final_score": final.score or 0,
        "improved_topics": [],
        "remaining_weak_topics": (latest_skill.skill_json.get("weak_topics", []) if latest_skill else []),
    }
    result_payload, meta = get_generation_provider(get_settings()).generate_result_summary(
        document_skill=_document_skill_json(session, run),
        learner_skill_history=[item.skill_json for item in session.scalars(select(LearnerSkillRevision).where(LearnerSkillRevision.run_id == run.id))],
        score_summary=score_summary,
    )
    summary = ResultSummary(
        run_id=run.id,
        initial_score=initial.score or 0,
        final_score=final.score or 0,
        gain_score=(final.score or 0) - (initial.score or 0),
        gain_rate=((final.score or 0) - (initial.score or 0)) / max(1, initial.max_score or 1),
        initial_accuracy=initial_accuracy,
        final_accuracy=final_accuracy,
        accuracy_gain=final_accuracy - initial_accuracy,
        cycle_score_trend=[
            {"cycle_index": index + 1, "score": attempt.score or 0, "max_score": attempt.max_score or 0}
            for index, attempt in enumerate(cycle_attempts)
        ],
        topic_mastery_before_after={},
        improved_topics=result_payload.improved_topics,
        remaining_weak_topics=result_payload.remaining_weak_topics,
        misconception_reduction=result_payload.misconception_reduction,
        material_read_duration_summary=_material_read_summary(session, run.id),
        test_duration_summary=_test_duration_summary([initial, *cycle_attempts, final]),
        ai_summary=result_payload.ai_summary,
    )
    session.add(summary)
    _log_generation(session, run.id, "result_summary", score_summary, result_payload.model_dump(mode="json"), "valid", meta)
    session.flush()
    return summary


def _latest_attempt_for(session: Session, run_id: str, assessment_type: str, cycle_index: int | None) -> AssessmentAttempt:
    assessment = _latest_assessment(session, run_id, assessment_type, cycle_index)
    attempt = session.scalar(
        select(AssessmentAttempt)
        .where(AssessmentAttempt.assessment_id == assessment.id)
        .order_by(AssessmentAttempt.created_at.desc())
        .limit(1)
    )
    if not attempt:
        raise HTTPException(status_code=409, detail=f"{assessment_type} attempt is missing")
    return attempt


def _material_read_summary(session: Session, run_id: str) -> dict:
    rows = list(session.scalars(select(MaterialRead).where(MaterialRead.run_id == run_id)))
    total = sum(row.read_duration_seconds for row in rows)
    return {"count": len(rows), "total_seconds": total, "average_seconds": total / len(rows) if rows else 0}


def _test_duration_summary(attempts: list[AssessmentAttempt]) -> dict:
    durations = [attempt.duration_seconds or 0 for attempt in attempts]
    return {"count": len(durations), "total_seconds": sum(durations), "average_seconds": sum(durations) / len(durations) if durations else 0}


def _log_generation(session: Session, run_id: str | None, generation_type: str, input_summary: dict, output: dict, validation_status: str, provider_meta, error: str | None = None) -> None:
    session.add(
        GenerationLog(
            run_id=run_id,
            generation_type=generation_type,
            input_summary_json=input_summary,
            output_json=output,
            validation_status=validation_status,
            error_message=error,
            provider=provider_meta.provider_name,
            model=provider_meta.model_name,
            prompt_version=provider_meta.prompt_version,
            temperature=provider_meta.temperature,
            input_schema_version="v1",
            output_schema_version="v1",
            generated_at=utcnow(),
        )
    )


def _next_action(run: ExperimentRun) -> str:
    if run.state == "RUN_STARTED":
        return "generate_initial_test"
    if run.state == "INITIAL_TEST_GENERATED":
        return "submit_initial_test"
    if run.state in {"INITIAL_TEST_SUBMITTED", "CYCLE_TEST_SUBMITTED"} and run.current_cycle_index <= run.cycle_count:
        return f"generate_cycle_{run.current_cycle_index}_material"
    if run.state == "CYCLE_MATERIAL_GENERATED":
        return f"confirm_cycle_{run.current_cycle_index}_material_read"
    if run.state == "CYCLE_MATERIAL_READ":
        return f"generate_cycle_{run.current_cycle_index}_test"
    if run.state == "CYCLE_TEST_GENERATED":
        return f"submit_cycle_{run.current_cycle_index}_test"
    if run.state == "CYCLE_TEST_SUBMITTED" and run.current_cycle_index == run.cycle_count:
        return "generate_final_test"
    if run.state == "FINAL_TEST_GENERATED":
        return "submit_final_test"
    if run.state in {"FINAL_TEST_SUBMITTED", "RESULT_READY"}:
        return "view_results"
    return "unknown"


def _build_csv_payloads(session: Session, run_id: str | None) -> dict[str, str]:
    def rows_to_csv(name: str, rows: list[dict]) -> tuple[str, str]:
        buffer = io.StringIO()
        fieldnames = sorted({key for row in rows for key in row.keys()}) or ["empty"]
        writer = csv.DictWriter(buffer, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in fieldnames})
        return name, buffer.getvalue()

    run_filter = [ExperimentRun.id == run_id] if run_id else []
    runs = list(session.scalars(select(ExperimentRun).where(*run_filter)))
    run_ids = [run.id for run in runs]
    assessment_filter = [GeneratedAssessment.run_id.in_(run_ids)] if run_id else []

    payloads = dict(
        [
            rows_to_csv("runs.csv", [_model_dict(run) for run in runs]),
            rows_to_csv("source_documents.csv", [_model_dict(row) for row in session.scalars(select(SourceDocument))]),
            rows_to_csv("document_skill_revisions.csv", [_model_dict(row) for row in session.scalars(select(AdaptiveDocumentSkillRevision))]),
            rows_to_csv("document_skill_entries.csv", [_model_dict(row) for row in session.scalars(select(AdaptiveDocumentSkillEntry))]),
            rows_to_csv("generated_assessments.csv", [_model_dict(row) for row in session.scalars(select(GeneratedAssessment).where(*assessment_filter))]),
            rows_to_csv("assessment_items.csv", [_model_dict(row) for row in session.scalars(select(AssessmentItem))]),
            rows_to_csv("assessment_attempts.csv", [_model_dict(row) for row in session.scalars(select(AssessmentAttempt)) if (not run_id or row.run_id == run_id)]),
            rows_to_csv("generated_materials.csv", [_model_dict(row) for row in session.scalars(select(GeneratedMaterial)) if (not run_id or row.run_id == run_id)]),
            rows_to_csv("material_reads.csv", [_model_dict(row) for row in session.scalars(select(MaterialRead)) if (not run_id or row.run_id == run_id)]),
            rows_to_csv("learner_skill_revisions.csv", [_model_dict(row) for row in session.scalars(select(LearnerSkillRevision)) if (not run_id or row.run_id == run_id)]),
            rows_to_csv("generation_logs.csv", [_model_dict(row) for row in session.scalars(select(GenerationLog)) if (not run_id or row.run_id == run_id)]),
            rows_to_csv("result_summaries.csv", [_model_dict(row) for row in session.scalars(select(ResultSummary)) if (not run_id or row.run_id == run_id)]),
        ]
    )
    return payloads


def _model_dict(row: Any) -> dict:
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


def _csv_value(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return ""
    return str(value)
