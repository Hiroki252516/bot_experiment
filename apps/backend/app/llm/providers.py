from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.schemas.adaptive import (
    AssessmentPayload,
    DocumentSkillPayload,
    GeneratedMaterialPayload,
    LearnerSkillPayload,
    ResultSummaryPayload,
)
from app.schemas.document_skill import DocumentSkillDelta
from app.schemas.llm import GeneratedCandidateSet, ProviderMetadata, SkillDelta


CANDIDATE_MARKDOWN_INSTRUCTIONS = (
    "Keep title as short plain text. Do not put Markdown heading markers such as ## in title.\n"
    "For every candidate, write answer_text as learner-facing Markdown.\n"
    "Use short sections with headings such as '## 概要', '## 要点', '## 手順' or '## 注意点'.\n"
    "Use blank lines between sections, and use bullet lists or numbered lists for details.\n"
    "Do not write answer_text as one long paragraph.\n"
    "Organize Document Skill entries into readable chunks, while keeping each candidate's explanation style distinct.\n"
    "Do not wrap the whole answer_text in a markdown code fence.\n"
)


class GenerationProvider(ABC):
    provider_name: str

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @abstractmethod
    def generate_candidates(
        self,
        question: str,
        preference_skill_profile: dict,
        document_skill_context: dict,
        candidate_count: int,
        personalization_skills_enabled: bool,
        document_skills_enabled: bool,
    ) -> tuple[GeneratedCandidateSet, ProviderMetadata]:
        raise NotImplementedError

    @abstractmethod
    def extract_skill_delta(
        self,
        previous_skill: dict,
        chosen_candidate: dict,
        rejected_candidates: list[dict],
        user_comment: str | None,
    ) -> tuple[SkillDelta, ProviderMetadata]:
        raise NotImplementedError

    @abstractmethod
    def extract_document_skill_delta(
        self,
        document_metadata: dict,
        source_unit: dict,
        previous_document_skill: dict,
    ) -> tuple[DocumentSkillDelta, ProviderMetadata]:
        raise NotImplementedError

    def generate_material(
        self,
        cycle_index: int,
        skill_profile: dict,
        skills_enabled: bool,
        document_skill_context: dict | None = None,
    ) -> tuple[dict[str, Any], ProviderMetadata]:
        raise NotImplementedError

    def generate_assessment(
        self,
        assessment_type: str,
        cycle_index: int | None,
        material_text: str | None,
        document_skill_context: dict,
        skill_profile: dict,
        skills_enabled: bool,
    ) -> tuple[dict[str, Any], ProviderMetadata]:
        raise NotImplementedError

    def answer_question(
        self,
        material_text: str,
        question_text: str,
        skill_profile: dict,
        skills_enabled: bool,
        document_skill_context: dict | None = None,
    ) -> tuple[dict[str, Any], ProviderMetadata]:
        raise NotImplementedError

    def extract_document_skill(
        self,
        document_metadata: dict,
        source_text: str,
    ) -> tuple[DocumentSkillPayload, ProviderMetadata]:
        raise NotImplementedError

    def generate_initial_test(
        self,
        document_skill: dict,
        question_count: int,
        used_fingerprints: list[str],
    ) -> tuple[AssessmentPayload, ProviderMetadata]:
        raise NotImplementedError

    def analyze_attempt_and_create_learner_skill(
        self,
        document_skill: dict,
        assessment: dict,
        attempt: dict,
        revision: int,
        previous_skill: dict | None = None,
    ) -> tuple[LearnerSkillPayload, ProviderMetadata]:
        raise NotImplementedError

    def generate_learning_material(
        self,
        document_skill: dict,
        learner_skill: dict,
        cycle_index: int,
    ) -> tuple[GeneratedMaterialPayload, ProviderMetadata]:
        raise NotImplementedError

    def generate_cycle_test(
        self,
        document_skill: dict,
        learner_skill: dict,
        cycle_index: int,
        question_count: int,
        used_fingerprints: list[str],
    ) -> tuple[AssessmentPayload, ProviderMetadata]:
        raise NotImplementedError

    def update_learner_skill(
        self,
        document_skill: dict,
        previous_skill: dict,
        assessment: dict,
        attempt: dict,
        revision: int,
    ) -> tuple[LearnerSkillPayload, ProviderMetadata]:
        return self.analyze_attempt_and_create_learner_skill(
            document_skill=document_skill,
            assessment=assessment,
            attempt=attempt,
            revision=revision,
            previous_skill=previous_skill,
        )

    def generate_final_test(
        self,
        document_skill: dict,
        question_count: int,
        used_fingerprints: list[str],
    ) -> tuple[AssessmentPayload, ProviderMetadata]:
        return self.generate_initial_test(document_skill, question_count, used_fingerprints)

    def generate_result_summary(
        self,
        document_skill: dict,
        learner_skill_history: list[dict],
        score_summary: dict,
    ) -> tuple[ResultSummaryPayload, ProviderMetadata]:
        raise NotImplementedError


class MockGenerationProvider(GenerationProvider):
    provider_name = "mock"

    def generate_candidates(
        self,
        question: str,
        preference_skill_profile: dict,
        document_skill_context: dict,
        candidate_count: int,
        personalization_skills_enabled: bool,
        document_skills_enabled: bool,
    ) -> tuple[GeneratedCandidateSet, ProviderMetadata]:
        styles = [
            ("Hint-first", ["hint-first", "stepwise"]),
            ("Worked example", ["example-first", "concrete"]),
            ("Concise summary", ["short", "direct"]),
            ("Socratic coach", ["socratic", "guided"]),
            ("Evidence-led", ["context-citing", "structured"]),
        ]
        documents = document_skill_context.get("documents", []) if document_skills_enabled else []
        entries = documents[0].get("entries", []) if documents else []
        cited_context = entries[0].get("content", "")[:180] if entries else "資料中に該当する Document Skill entry がありません。"
        notes = ", ".join(preference_skill_profile.get("notes", [])) if personalization_skills_enabled else "preference skills disabled"
        candidates = []
        for rank in range(candidate_count):
            title, style_tags = styles[rank]
            answer_text = (
                f"## 概要\n\n"
                f"**{title}** の方針で、質問「{question}」に答えます。\n\n"
                f"## 教材から拾った要点\n\n"
                f"- {cited_context}\n"
                f"- スキル反映: {notes}\n\n"
                f"## 説明の進め方\n\n"
                f"1. まず重要な考え方を短く確認します。\n"
                f"2. 次に学習者が迷いやすい点を整理します。\n"
                f"3. 最後に自分で確認できるチェックポイントを示します。"
            )
            candidates.append(
                {
                    "title": title,
                    "style_tags": style_tags,
                    "answer_text": answer_text,
                    "rationale": f"Mock candidate {rank + 1} emphasizing {'/'.join(style_tags)}.",
                }
            )
        return (
            GeneratedCandidateSet.model_validate({"candidates": candidates}),
            ProviderMetadata(
                provider_name=self.provider_name,
                model_name="mock-model",
                temperature=self.settings.generation_temperature,
                top_p=self.settings.generation_top_p,
                prompt_version=self.settings.prompt_version,
                raw_response={"mode": "mock"},
            ),
        )

    def extract_document_skill_delta(
        self,
        document_metadata: dict,
        source_unit: dict,
        previous_document_skill: dict,
    ) -> tuple[DocumentSkillDelta, ProviderMetadata]:
        text = str(source_unit.get("text", "")).strip()
        page = source_unit.get("source_page")
        lines = [line.strip(" -・\t") for line in text.splitlines() if line.strip()]
        facts = []
        procedures = []
        warnings = []
        for line in lines[:12]:
            source_pages = [page] if page is not None else []
            if any(keyword in line for keyword in ["課題", "提出", "作成", "手順", "フォルダ", "ファイル"]):
                procedures.append({"title": line[:80], "steps": [line], "source_pages": source_pages})
            elif any(keyword in line for keyword in ["注意", "禁止", "必要", "不可"]):
                warnings.append(line)
            else:
                facts.append({"statement": line, "source_pages": source_pages})
        if not procedures and text:
            procedures.append(
                {
                    "title": "教材内容の要点",
                    "steps": [line for line in lines[:4]] or [text[:240]],
                    "source_pages": [page] if page is not None else [],
                }
            )
        delta = DocumentSkillDelta.model_validate(
            {
                "document_title": document_metadata.get("filename", ""),
                "summary": text[:500],
                "facts": facts[:8],
                "procedures": procedures[:5],
                "warnings": warnings[:5],
                "source_map": [
                    {
                        "excerpt": text[:500],
                        "page": page,
                        "source_span": source_unit.get("source_span"),
                    }
                ]
                if text
                else [],
            }
        )
        return (
            delta,
            ProviderMetadata(
                provider_name=self.provider_name,
                model_name="mock-model",
                temperature=self.settings.generation_temperature,
                top_p=self.settings.generation_top_p,
                prompt_version=self.settings.prompt_version,
                raw_response={"mode": "mock-document-skill"},
            ),
        )

    def extract_skill_delta(
        self,
        previous_skill: dict,
        chosen_candidate: dict,
        rejected_candidates: list[dict],
        user_comment: str | None,
    ) -> tuple[SkillDelta, ProviderMetadata]:
        disliked = []
        rejected_tags = {tag for candidate in rejected_candidates for tag in candidate.get("style_tags", [])}
        for tag in sorted(rejected_tags):
            if "short" in tag or "direct" in tag:
                disliked.append("answer-only")
                break
        delta = SkillDelta.model_validate(
            {
                "add_preferences": {
                    "preferred_explanation_style": chosen_candidate.get("style_tags", [])[:1],
                    "preferred_structure_pattern": ["example-then-steps-then-check"]
                    if "example-first" in chosen_candidate.get("style_tags", [])
                    else ["steps-then-check"],
                    "preferred_hint_level": "medium",
                    "preferred_answer_length": "medium",
                    "evidence_preference": "cite-retrieved-context",
                },
                "add_dislikes": disliked,
                "summary_rule": user_comment
                or f"Prefer responses similar to {chosen_candidate.get('title', 'selected candidate')}.",
            }
        )
        return (
            delta,
            ProviderMetadata(
                provider_name=self.provider_name,
                model_name="mock-model",
                temperature=self.settings.generation_temperature,
                top_p=self.settings.generation_top_p,
                prompt_version=self.settings.prompt_version,
                raw_response={"mode": "mock"},
            ),
        )

    def generate_material(
        self,
        cycle_index: int,
        skill_profile: dict,
        skills_enabled: bool,
        document_skill_context: dict | None = None,
    ) -> tuple[dict[str, Any], ProviderMetadata]:
        notes = ", ".join(skill_profile.get("notes", [])) if skills_enabled else "skills disabled"
        context = _document_skill_context_excerpt(document_skill_context or {})
        content_text = (
            f"# 教材（Cycle {cycle_index}）\n\n"
            "この教材はアップロード教材の内容をもとにした学習サイクル用テキストです。\n\n"
            f"- スキル反映: {notes}\n\n"
            f"## アップロード教材からの要点\n\n{context}\n\n"
            "## 要点\n\n"
            "1. アップロード教材の重要事項を確認する\n"
            "2. 具体例や提出条件を整理する\n"
            "3. ミニテストで確認する観点を押さえる\n"
        )
        return (
            {
                "title": f"教材 {cycle_index}",
                "difficulty": "medium",
                "learning_objectives": ["理解度チェック"],
                "content_text": content_text,
            },
            ProviderMetadata(
                provider_name=self.provider_name,
                model_name="mock-model",
                temperature=self.settings.generation_temperature,
                top_p=self.settings.generation_top_p,
                prompt_version=self.settings.prompt_version,
                raw_response={"mode": "mock-material"},
            ),
        )

    def generate_assessment(
        self,
        assessment_type: str,
        cycle_index: int | None,
        material_text: str | None,
        document_skill_context: dict,
        skill_profile: dict,
        skills_enabled: bool,
    ) -> tuple[dict[str, Any], ProviderMetadata]:
        excerpt = _document_skill_context_excerpt(document_skill_context)
        prefix = "Pre" if assessment_type == "pre_test" else "Post" if assessment_type == "post_test" else f"Mini{cycle_index}"
        topic = (material_text or excerpt).replace("\n", " ")[:60] or "アップロード教材"
        return (
            {
                "questions": [
                    {
                        "question_id": f"{prefix}_q1",
                        "stem": f"アップロード教材に基づく確認です。次のうち教材内容に最も合うものはどれですか？（{topic}）",
                        "choices": [excerpt[:120] or topic, "教材にない一般的な説明", "無関係な選択肢", "判断できない"],
                        "correct_choice_index": 0,
                    },
                    {
                        "question_id": f"{prefix}_q2",
                        "stem": "教材を読むときに最も重視すべきことはどれですか？",
                        "choices": ["教材に書かれた条件や手順を確認する", "教材と無関係な知識だけを暗記する", "問題文を読まずに選ぶ", "提出条件を無視する"],
                        "correct_choice_index": 0,
                    },
                ]
            },
            ProviderMetadata(
                provider_name=self.provider_name,
                model_name="mock-model",
                temperature=self.settings.generation_temperature,
                top_p=self.settings.generation_top_p,
                prompt_version=self.settings.prompt_version,
                raw_response={"mode": "mock-assessment"},
            ),
        )

    def answer_question(
        self,
        material_text: str,
        question_text: str,
        skill_profile: dict,
        skills_enabled: bool,
        document_skill_context: dict | None = None,
    ) -> tuple[dict[str, Any], ProviderMetadata]:
        notes = ", ".join(skill_profile.get("notes", [])) if skills_enabled else "skills disabled"
        context = _document_skill_context_excerpt(document_skill_context or {})
        answer_text = (
            "教材の要点に沿って説明します。\n\n"
            f"- 質問: {question_text}\n"
            f"- スキル反映: {notes}\n\n"
            f"## アップロード教材からの根拠\n\n{context}\n\n"
            "不明点があれば、教材のどの段落かを指定して追加で質問してください。"
        )
        return (
            {"answer_text": answer_text},
            ProviderMetadata(
                provider_name=self.provider_name,
                model_name="mock-model",
                temperature=self.settings.generation_temperature,
                top_p=self.settings.generation_top_p,
                prompt_version=self.settings.prompt_version,
                raw_response={"mode": "mock-answer"},
            ),
        )

    def _adaptive_meta(self, mode: str) -> ProviderMetadata:
        return ProviderMetadata(
            provider_name=self.provider_name,
            model_name="mock-model",
            temperature=self.settings.generation_temperature,
            top_p=self.settings.generation_top_p,
            prompt_version=self.settings.prompt_version,
            raw_response={"mode": mode},
        )

    def extract_document_skill(
        self,
        document_metadata: dict,
        source_text: str,
    ) -> tuple[DocumentSkillPayload, ProviderMetadata]:
        title = document_metadata.get("title") or document_metadata.get("filename") or "教材"
        lines = [line.strip(" -・\t") for line in source_text.splitlines() if line.strip()]
        topics = lines[:5] or [title]
        payload = DocumentSkillPayload.model_validate(
            {
                "learning_objectives": [f"{topic[:80]}を理解する" for topic in topics[:3]],
                "topic_map": [{"topic_key": f"topic_{i}", "title": topic[:80]} for i, topic in enumerate(topics, start=1)],
                "concept_definitions": [
                    {"term": topic[:40], "definition": topic[:240], "topic_key": f"topic_{i}"}
                    for i, topic in enumerate(topics[:5], start=1)
                ],
                "prerequisite_concepts": [],
                "examples": [{"title": "教材例", "content": (source_text[:500] or title)}],
                "common_misconceptions": ["キーワードだけを暗記し、条件や例外を確認しない"],
                "difficulty_map": [{"topic_key": "topic_1", "difficulty": "basic"}],
                "assessment_blueprint": [{"topic_key": "topic_1", "weight": 1.0, "difficulty": "basic"}],
                "canonical_explanations": [{"topic_key": "topic_1", "content": source_text[:800] or title}],
                "out_of_scope": [],
                "source_pdf_metadata": document_metadata,
                "revision": 1,
            }
        )
        return payload, self._adaptive_meta("mock-document-skill")

    def _mock_assessment(
        self,
        title: str,
        prefix: str,
        question_count: int,
        used_fingerprints: list[str],
        focus_topics: list[str] | None = None,
    ) -> AssessmentPayload:
        topics = focus_topics or ["topic_1"]
        questions = []
        used = set(used_fingerprints)
        for index in range(1, question_count + 1):
            topic = topics[(index - 1) % len(topics)] if topics else "topic_1"
            fingerprint = f"{prefix}_{index}_{topic}".lower()
            suffix = 0
            while fingerprint in used:
                suffix += 1
                fingerprint = f"{prefix}_{index}_{topic}_{suffix}".lower()
            used.add(fingerprint)
            questions.append(
                {
                    "question_id": f"{prefix}_q{index}",
                    "topic": topic,
                    "subtopic": "",
                    "difficulty": "basic" if index % 3 == 1 else "standard" if index % 3 == 2 else "advanced",
                    "stem": f"{topic} について、教材内容に最も合う説明を選んでください。",
                    "choices": ["教材内容に沿った説明", "教材範囲外の説明", "誤った一般化", "判断できない"],
                    "correct_answer": "教材内容に沿った説明",
                    "rubric": "正答は教材内容に沿った説明。",
                    "fingerprint": fingerprint,
                }
            )
        return AssessmentPayload.model_validate({"title": title, "questions": questions, "blueprint": {"mock": True}})

    def generate_initial_test(
        self,
        document_skill: dict,
        question_count: int,
        used_fingerprints: list[str],
    ) -> tuple[AssessmentPayload, ProviderMetadata]:
        topics = [str(item.get("topic_key") or item.get("title") or "topic_1") for item in document_skill.get("topic_map", [])]
        return self._mock_assessment("初回テスト", "initial", question_count, used_fingerprints, topics), self._adaptive_meta("mock-initial-test")

    def analyze_attempt_and_create_learner_skill(
        self,
        document_skill: dict,
        assessment: dict,
        attempt: dict,
        revision: int,
        previous_skill: dict | None = None,
    ) -> tuple[LearnerSkillPayload, ProviderMetadata]:
        per_question = attempt.get("per_question_correct", [])
        questions = {q.get("question_id"): q for q in assessment.get("questions", [])}
        topic_totals: dict[str, list[int]] = {}
        for result in per_question:
            question = questions.get(result.get("question_id"), {})
            topic = str(question.get("topic") or "topic_1")
            topic_totals.setdefault(topic, []).append(1 if result.get("is_correct") else 0)
        mastery = {
            topic: sum(values) / max(1, len(values))
            for topic, values in topic_totals.items()
        }
        known = [topic for topic, value in mastery.items() if value >= 0.7]
        weak = [topic for topic, value in mastery.items() if value < 0.7] or list(mastery)[:1]
        used = list((previous_skill or {}).get("used_question_fingerprints", []))
        used.extend([str(q.get("fingerprint", "")) for q in assessment.get("questions", []) if q.get("fingerprint")])
        payload = LearnerSkillPayload.model_validate(
            {
                "overall_mastery": attempt.get("score", 0) / max(1, attempt.get("max_score", 1)),
                "mastery_by_topic": mastery,
                "known_topics": known,
                "weak_topics": weak,
                "common_mistakes": ["不正解だった設問の概念を再確認する"],
                "misconception_hypotheses": ["選択肢の細部を読み落としている可能性"],
                "recommended_next_focus": weak,
                "recommended_difficulty": "basic" if weak else "standard",
                "generated_material_history_summary": (previous_skill or {}).get("generated_material_history_summary", []),
                "used_question_fingerprints": list(dict.fromkeys(used)),
                "evidence_from_attempts": [{"attempt": attempt}],
                "revision": revision,
            }
        )
        return payload, self._adaptive_meta("mock-learner-skill")

    def generate_learning_material(
        self,
        document_skill: dict,
        learner_skill: dict,
        cycle_index: int,
    ) -> tuple[GeneratedMaterialPayload, ProviderMetadata]:
        weak_topics = learner_skill.get("weak_topics", []) or learner_skill.get("recommended_next_focus", []) or ["topic_1"]
        payload = GeneratedMaterialPayload.model_validate(
            {
                "title": f"Cycle {cycle_index}: 弱点補強教材",
                "learning_goals": [f"{topic}を説明できる" for topic in weak_topics],
                "body": "\n\n".join(
                    [
                        f"# Cycle {cycle_index} 弱点補強教材",
                        "この教材は Document Agent Skill と Learner Agent Skill に基づいて生成された研究用教材です。",
                        "## 重点項目",
                        "\n".join(f"- {topic}" for topic in weak_topics),
                        "## 解説",
                        "教材の定義、例、よくある誤りを確認しながら、次のテストで問われる観点を整理してください。",
                    ]
                ),
                "examples": ["教材中の例を自分の言葉で説明する"],
                "common_mistakes": learner_skill.get("common_mistakes", []),
                "checkpoints": [f"{topic}の要点を説明できる" for topic in weak_topics],
                "target_topics": weak_topics,
                "difficulty": learner_skill.get("recommended_difficulty", "basic"),
            }
        )
        return payload, self._adaptive_meta("mock-material-v2")

    def generate_cycle_test(
        self,
        document_skill: dict,
        learner_skill: dict,
        cycle_index: int,
        question_count: int,
        used_fingerprints: list[str],
    ) -> tuple[AssessmentPayload, ProviderMetadata]:
        topics = learner_skill.get("weak_topics", []) or learner_skill.get("recommended_next_focus", []) or ["topic_1"]
        return self._mock_assessment(
            f"Cycle {cycle_index} テスト",
            f"cycle{cycle_index}",
            question_count,
            used_fingerprints,
            topics,
        ), self._adaptive_meta("mock-cycle-test")

    def generate_final_test(
        self,
        document_skill: dict,
        question_count: int,
        used_fingerprints: list[str],
    ) -> tuple[AssessmentPayload, ProviderMetadata]:
        topics = [str(item.get("topic_key") or item.get("title") or "topic_1") for item in document_skill.get("topic_map", [])]
        return self._mock_assessment("最終テスト", "final", question_count, used_fingerprints, topics), self._adaptive_meta("mock-final-test")

    def generate_result_summary(
        self,
        document_skill: dict,
        learner_skill_history: list[dict],
        score_summary: dict,
    ) -> tuple[ResultSummaryPayload, ProviderMetadata]:
        payload = ResultSummaryPayload.model_validate(
            {
                "ai_summary": (
                    f"初回 {score_summary.get('initial_score', 0)} 点から最終 "
                    f"{score_summary.get('final_score', 0)} 点になりました。"
                ),
                "improved_topics": score_summary.get("improved_topics", []),
                "remaining_weak_topics": score_summary.get("remaining_weak_topics", []),
                "misconception_reduction": {},
            }
        )
        return payload, self._adaptive_meta("mock-result-summary")


class GeminiGenerationProvider(GenerationProvider):
    provider_name = "gemini"

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.settings.gemini_api_base_url,
            headers={"x-goog-api-key": self.settings.gemini_api_key, "Content-Type": "application/json"},
            timeout=self.settings.request_timeout_seconds,
        )

    def _generate_json(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        if not self.settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is required when GENERATION_PROVIDER=gemini")
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": self.settings.generation_temperature,
                "topP": self.settings.generation_top_p,
                "response_mime_type": "application/json",
                "response_schema": schema,
            },
        }
        with self._client() as client:
            response = client.post(f"/models/{self.settings.gemini_model_generate}:generateContent", json=body)
            response.raise_for_status()
            payload = response.json()
        text_parts = payload["candidates"][0]["content"]["parts"]
        text_value = "".join(part.get("text", "") for part in text_parts)
        return {"parsed": json.loads(text_value), "raw": payload}

    def generate_candidates(
        self,
        question: str,
        preference_skill_profile: dict,
        document_skill_context: dict,
        candidate_count: int,
        personalization_skills_enabled: bool,
        document_skills_enabled: bool,
    ) -> tuple[GeneratedCandidateSet, ProviderMetadata]:
        schema = {
            "type": "OBJECT",
            "properties": {
                "candidates": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "title": {"type": "STRING"},
                            "style_tags": {"type": "ARRAY", "items": {"type": "STRING"}},
                            "answer_text": {"type": "STRING"},
                            "rationale": {"type": "STRING"},
                        },
                        "required": ["title", "style_tags", "answer_text", "rationale"],
                    },
                }
            },
            "required": ["candidates"],
        }
        prompt = (
            "You are generating tutoring answer candidates for a research system.\n"
            f"{CANDIDATE_MARKDOWN_INSTRUCTIONS}"
            f"Question: {question}\n"
            f"Candidate count: {candidate_count}\n"
            f"Personalization skills enabled: {personalization_skills_enabled}\n"
            f"Document skills enabled: {document_skills_enabled}\n"
            f"Preference Skill JSON: {json.dumps(preference_skill_profile, ensure_ascii=False)}\n"
            f"Document Agent Skills JSON: {json.dumps(document_skill_context, ensure_ascii=False)}\n"
            "Use Document Agent Skills as the source of truth for material-specific facts.\n"
            "If no relevant Document Skill entry is present, say that the matching passage was not found in the material.\n"
            "Return exactly the requested number of distinct learner-facing candidates."
        )
        last_error: Exception | None = None
        for _ in range(2):
            try:
                result = self._generate_json(prompt, schema)
                parsed = GeneratedCandidateSet.model_validate(result["parsed"])
                if len(parsed.candidates) != candidate_count:
                    raise ValueError("candidate count mismatch")
                metadata = ProviderMetadata(
                    provider_name=self.provider_name,
                    model_name=self.settings.gemini_model_generate,
                    temperature=self.settings.generation_temperature,
                    top_p=self.settings.generation_top_p,
                    prompt_version=self.settings.prompt_version,
                    raw_response=result["raw"],
                )
                return parsed, metadata
            except Exception as exc:
                last_error = exc
        raise RuntimeError(f"Gemini candidate generation failed: {last_error}") from last_error

    def extract_skill_delta(
        self,
        previous_skill: dict,
        chosen_candidate: dict,
        rejected_candidates: list[dict],
        user_comment: str | None,
    ) -> tuple[SkillDelta, ProviderMetadata]:
        schema = {
            "type": "OBJECT",
            "properties": {
                "add_preferences": {
                    "type": "OBJECT",
                    "properties": {
                        "preferred_explanation_style": {"type": "ARRAY", "items": {"type": "STRING"}},
                        "preferred_structure_pattern": {"type": "ARRAY", "items": {"type": "STRING"}},
                        "preferred_hint_level": {"type": "STRING"},
                        "preferred_answer_length": {"type": "STRING"},
                        "evidence_preference": {"type": "STRING"},
                    },
                },
                "add_dislikes": {"type": "ARRAY", "items": {"type": "STRING"}},
                "summary_rule": {"type": "STRING"},
            },
            "required": ["add_preferences", "add_dislikes", "summary_rule"],
        }
        prompt = (
            "You are extracting reusable learner preference rules.\n"
            f"Previous skill profile JSON: {json.dumps(previous_skill, ensure_ascii=False)}\n"
            f"Chosen candidate JSON: {json.dumps(chosen_candidate, ensure_ascii=False)}\n"
            f"Rejected candidates JSON: {json.dumps(rejected_candidates, ensure_ascii=False)}\n"
            f"User comment: {user_comment or ''}\n"
            "Return normalized preference deltas only."
        )
        result = self._generate_json(prompt, schema)
        return (
            SkillDelta.model_validate(result["parsed"]),
            ProviderMetadata(
                provider_name=self.provider_name,
                model_name=self.settings.gemini_model_generate,
                temperature=self.settings.generation_temperature,
                top_p=self.settings.generation_top_p,
                prompt_version=self.settings.prompt_version,
                raw_response=result["raw"],
            ),
        )

    def extract_document_skill_delta(
        self,
        document_metadata: dict,
        source_unit: dict,
        previous_document_skill: dict,
    ) -> tuple[DocumentSkillDelta, ProviderMetadata]:
        schema = _gemini_document_skill_delta_schema()
        prompt = _document_skill_prompt(document_metadata, source_unit, previous_document_skill)
        result = self._generate_json(prompt, schema)
        return (
            DocumentSkillDelta.model_validate(result["parsed"]),
            ProviderMetadata(
                provider_name=self.provider_name,
                model_name=self.settings.gemini_model_generate,
                temperature=self.settings.generation_temperature,
                top_p=self.settings.generation_top_p,
                prompt_version=self.settings.prompt_version,
                raw_response=result["raw"],
            ),
        )

    def generate_material(
        self,
        cycle_index: int,
        skill_profile: dict,
        skills_enabled: bool,
        document_skill_context: dict | None = None,
    ) -> tuple[dict[str, Any], ProviderMetadata]:
        schema = {
            "type": "OBJECT",
            "properties": {
                "title": {"type": "STRING"},
                "difficulty": {"type": "STRING"},
                "learning_objectives": {"type": "ARRAY", "items": {"type": "STRING"}},
                "content_text": {"type": "STRING"},
            },
            "required": ["title", "difficulty", "learning_objectives", "content_text"],
        }
        prompt = (
            "あなたは学習支援システムの教材（テキスト）を生成するAIです。\n"
            "必ず日本語で、学習者向けに分かりやすく書いてください。\n"
            "出力は必ず JSON で、指定スキーマに従ってください。\n"
            f"サイクル: {cycle_index}\n"
            f"スキル適用の有無: {skills_enabled}\n"
            f"学習者スキル（JSON）: {json.dumps(skill_profile, ensure_ascii=False)}\n"
            f"アップロード教材のDocument Skill（JSON）: {json.dumps(document_skill_context or {}, ensure_ascii=False)}\n"
            "教材本文は必ずアップロード教材の内容に基づいてください。一般論だけで書かないでください。\n"
        )
        result = self._generate_json(prompt, schema)
        return (
            result["parsed"],
            ProviderMetadata(
                provider_name=self.provider_name,
                model_name=self.settings.gemini_model_generate,
                temperature=self.settings.generation_temperature,
                top_p=self.settings.generation_top_p,
                prompt_version=self.settings.prompt_version,
                raw_response=result["raw"],
            ),
        )

    def generate_assessment(
        self,
        assessment_type: str,
        cycle_index: int | None,
        material_text: str | None,
        document_skill_context: dict,
        skill_profile: dict,
        skills_enabled: bool,
    ) -> tuple[dict[str, Any], ProviderMetadata]:
        schema = _gemini_assessment_schema()
        prompt = _study_assessment_prompt(assessment_type, cycle_index, material_text, document_skill_context, skill_profile, skills_enabled)
        result = self._generate_json(prompt, schema)
        return (
            result["parsed"],
            ProviderMetadata(
                provider_name=self.provider_name,
                model_name=self.settings.gemini_model_generate,
                temperature=self.settings.generation_temperature,
                top_p=self.settings.generation_top_p,
                prompt_version=self.settings.prompt_version,
                raw_response=result["raw"],
            ),
        )

    def answer_question(
        self,
        material_text: str,
        question_text: str,
        skill_profile: dict,
        skills_enabled: bool,
        document_skill_context: dict | None = None,
    ) -> tuple[dict[str, Any], ProviderMetadata]:
        schema = {"type": "OBJECT", "properties": {"answer_text": {"type": "STRING"}}, "required": ["answer_text"]}
        prompt = (
            "あなたは教材の読解支援チャットボットです。\n"
            "必ず日本語で回答し、教材の範囲に寄せて説明してください。\n"
            "出力は必ず JSON で、指定スキーマに従ってください。\n"
            f"スキル適用の有無: {skills_enabled}\n"
            f"学習者スキル（JSON）: {json.dumps(skill_profile, ensure_ascii=False)}\n"
            f"アップロード教材のDocument Skill（JSON）: {json.dumps(document_skill_context or {}, ensure_ascii=False)}\n"
            f"教材本文:\n{material_text}\n\n"
            f"学習者の質問: {question_text}\n"
        )
        result = self._generate_json(prompt, schema)
        return (
            result["parsed"],
            ProviderMetadata(
                provider_name=self.provider_name,
                model_name=self.settings.gemini_model_generate,
                temperature=self.settings.generation_temperature,
                top_p=self.settings.generation_top_p,
                prompt_version=self.settings.prompt_version,
                raw_response=result["raw"],
            ),
        )


class OllamaGenerationProvider(GenerationProvider):
    provider_name = "ollama"

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.settings.ollama_base_url,
            headers={"Content-Type": "application/json"},
            timeout=self.settings.ollama_request_timeout_seconds,
        )

    def _generate_json(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        body = {
            "model": self.settings.ollama_model_generate,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": schema,
            "options": {
                "temperature": self.settings.generation_temperature,
                "top_p": self.settings.generation_top_p,
            },
        }
        with self._client() as client:
            response = client.post("/api/chat", json=body)
            response.raise_for_status()
            payload = response.json()

        try:
            content = payload["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise RuntimeError("Ollama response missing message.content") from exc
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Ollama returned invalid JSON: {exc.msg}") from exc
        return {"parsed": parsed, "raw": payload}

    def generate_candidates(
        self,
        question: str,
        preference_skill_profile: dict,
        document_skill_context: dict,
        candidate_count: int,
        personalization_skills_enabled: bool,
        document_skills_enabled: bool,
    ) -> tuple[GeneratedCandidateSet, ProviderMetadata]:
        schema = {
            "type": "object",
            "properties": {
                "candidates": {
                    "type": "array",
                    "minItems": candidate_count,
                    "maxItems": candidate_count,
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "style_tags": {"type": "array", "items": {"type": "string"}},
                            "answer_text": {"type": "string"},
                            "rationale": {"type": "string"},
                        },
                        "required": ["title", "style_tags", "answer_text", "rationale"],
                    },
                }
            },
            "required": ["candidates"],
        }
        prompt = (
            "You are generating tutoring answer candidates for a research system.\n"
            "Return only JSON that matches the provided schema. Do not include markdown or commentary.\n"
            "The JSON object itself must not be markdown, but each candidate.answer_text must be Markdown text.\n"
            f"{CANDIDATE_MARKDOWN_INSTRUCTIONS}"
            f"Question: {question}\n"
            f"Candidate count: {candidate_count}\n"
            f"Personalization skills enabled: {personalization_skills_enabled}\n"
            f"Document skills enabled: {document_skills_enabled}\n"
            f"Preference Skill JSON: {json.dumps(preference_skill_profile, ensure_ascii=False)}\n"
            f"Document Agent Skills JSON: {json.dumps(document_skill_context, ensure_ascii=False)}\n"
            "Use Document Agent Skills as the source of truth for material-specific facts.\n"
            "If no relevant Document Skill entry is present, say that the matching passage was not found in the material.\n"
            "Return exactly the requested number of distinct learner-facing candidates."
        )
        try:
            result = self._generate_json(prompt, schema)
            parsed = GeneratedCandidateSet.model_validate(result["parsed"])
            if len(parsed.candidates) != candidate_count:
                raise RuntimeError(
                    f"Ollama candidate generation returned {len(parsed.candidates)} candidates; "
                    f"expected {candidate_count}"
                )
            metadata = ProviderMetadata(
                provider_name=self.provider_name,
                model_name=self.settings.ollama_model_generate,
                temperature=self.settings.generation_temperature,
                top_p=self.settings.generation_top_p,
                prompt_version=self.settings.prompt_version,
                raw_response=result["raw"],
            )
            return parsed, metadata
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Ollama candidate generation failed: {exc}") from exc

    def extract_skill_delta(
        self,
        previous_skill: dict,
        chosen_candidate: dict,
        rejected_candidates: list[dict],
        user_comment: str | None,
    ) -> tuple[SkillDelta, ProviderMetadata]:
        schema = {
            "type": "object",
            "properties": {
                "add_preferences": {
                    "type": "object",
                    "properties": {
                        "preferred_explanation_style": {"type": "array", "items": {"type": "string"}},
                        "preferred_structure_pattern": {"type": "array", "items": {"type": "string"}},
                        "preferred_hint_level": {"type": ["string", "null"]},
                        "preferred_answer_length": {"type": ["string", "null"]},
                        "evidence_preference": {"type": ["string", "null"]},
                    },
                    "required": [
                        "preferred_explanation_style",
                        "preferred_structure_pattern",
                        "preferred_hint_level",
                        "preferred_answer_length",
                        "evidence_preference",
                    ],
                },
                "add_dislikes": {"type": "array", "items": {"type": "string"}},
                "summary_rule": {"type": "string"},
            },
            "required": ["add_preferences", "add_dislikes", "summary_rule"],
        }
        prompt = (
            "You are extracting reusable learner preference rules.\n"
            "Return only JSON that matches the provided schema. Do not include markdown or commentary.\n"
            f"Previous skill profile JSON: {json.dumps(previous_skill, ensure_ascii=False)}\n"
            f"Chosen candidate JSON: {json.dumps(chosen_candidate, ensure_ascii=False)}\n"
            f"Rejected candidates JSON: {json.dumps(rejected_candidates, ensure_ascii=False)}\n"
            f"User comment: {user_comment or ''}\n"
            "Return normalized preference deltas only."
        )
        try:
            result = self._generate_json(prompt, schema)
            delta = SkillDelta.model_validate(result["parsed"])
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Ollama skill delta extraction failed: {exc}") from exc
        return (
            delta,
            ProviderMetadata(
                provider_name=self.provider_name,
                model_name=self.settings.ollama_model_generate,
                temperature=self.settings.generation_temperature,
                top_p=self.settings.generation_top_p,
                prompt_version=self.settings.prompt_version,
                raw_response=result["raw"],
            ),
        )

    def extract_document_skill_delta(
        self,
        document_metadata: dict,
        source_unit: dict,
        previous_document_skill: dict,
    ) -> tuple[DocumentSkillDelta, ProviderMetadata]:
        schema = _ollama_document_skill_delta_schema()
        prompt = _document_skill_prompt(document_metadata, source_unit, previous_document_skill)
        try:
            result = self._generate_json(prompt, schema)
            delta = DocumentSkillDelta.model_validate(result["parsed"])
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Ollama document skill extraction failed: {exc}") from exc
        return (
            delta,
            ProviderMetadata(
                provider_name=self.provider_name,
                model_name=self.settings.ollama_model_generate,
                temperature=self.settings.generation_temperature,
                top_p=self.settings.generation_top_p,
                prompt_version=self.settings.prompt_version,
                raw_response=result["raw"],
            ),
        )

    def generate_material(
        self,
        cycle_index: int,
        skill_profile: dict,
        skills_enabled: bool,
        document_skill_context: dict | None = None,
    ) -> tuple[dict[str, Any], ProviderMetadata]:
        schema = {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "difficulty": {"type": "string"},
                "learning_objectives": {"type": "array", "items": {"type": "string"}},
                "content_text": {"type": "string"},
            },
            "required": ["title", "difficulty", "learning_objectives", "content_text"],
        }
        prompt = (
            "あなたは学習支援システムの教材（テキスト）を生成するAIです。必ず日本語で回答してください。\n"
            "出力は必ず JSON で、指定スキーマに従ってください。\n"
            f"サイクル: {cycle_index}\n"
            f"スキル適用の有無: {skills_enabled}\n"
            f"学習者スキル（JSON）: {json.dumps(skill_profile, ensure_ascii=False)}\n"
            f"アップロード教材のDocument Skill（JSON）: {json.dumps(document_skill_context or {}, ensure_ascii=False)}\n"
            "教材本文は必ずアップロード教材の内容に基づいてください。一般論だけで書かないでください。\n"
        )
        result = self._generate_json(prompt, schema)
        return (
            result["parsed"],
            ProviderMetadata(
                provider_name=self.provider_name,
                model_name=self.settings.ollama_model_generate,
                temperature=self.settings.generation_temperature,
                top_p=self.settings.generation_top_p,
                prompt_version=self.settings.prompt_version,
                raw_response=result["raw"],
            ),
        )

    def generate_assessment(
        self,
        assessment_type: str,
        cycle_index: int | None,
        material_text: str | None,
        document_skill_context: dict,
        skill_profile: dict,
        skills_enabled: bool,
    ) -> tuple[dict[str, Any], ProviderMetadata]:
        schema = _ollama_assessment_schema()
        prompt = _study_assessment_prompt(assessment_type, cycle_index, material_text, document_skill_context, skill_profile, skills_enabled)
        result = self._generate_json(prompt, schema)
        return (
            result["parsed"],
            ProviderMetadata(
                provider_name=self.provider_name,
                model_name=self.settings.ollama_model_generate,
                temperature=self.settings.generation_temperature,
                top_p=self.settings.generation_top_p,
                prompt_version=self.settings.prompt_version,
                raw_response=result["raw"],
            ),
        )

    def answer_question(
        self,
        material_text: str,
        question_text: str,
        skill_profile: dict,
        skills_enabled: bool,
        document_skill_context: dict | None = None,
    ) -> tuple[dict[str, Any], ProviderMetadata]:
        schema = {"type": "object", "properties": {"answer_text": {"type": "string"}}, "required": ["answer_text"]}
        prompt = (
            "あなたは教材の読解支援チャットボットです。必ず日本語で回答し、教材の範囲に寄せて説明してください。\n"
            "出力は必ず JSON で、指定スキーマに従ってください。\n"
            f"スキル適用の有無: {skills_enabled}\n"
            f"学習者スキル（JSON）: {json.dumps(skill_profile, ensure_ascii=False)}\n"
            f"アップロード教材のDocument Skill（JSON）: {json.dumps(document_skill_context or {}, ensure_ascii=False)}\n"
            f"教材本文:\n{material_text}\n\n"
            f"学習者の質問: {question_text}\n"
        )
        result = self._generate_json(prompt, schema)
        return (
            result["parsed"],
            ProviderMetadata(
                provider_name=self.provider_name,
                model_name=self.settings.ollama_model_generate,
                temperature=self.settings.generation_temperature,
                top_p=self.settings.generation_top_p,
                prompt_version=self.settings.prompt_version,
                raw_response=result["raw"],
            ),
        )

    def _adaptive_metadata(self, raw: dict[str, Any]) -> ProviderMetadata:
        return ProviderMetadata(
            provider_name=self.provider_name,
            model_name=self.settings.ollama_model_generate,
            temperature=self.settings.generation_temperature,
            top_p=self.settings.generation_top_p,
            prompt_version=self.settings.prompt_version,
            raw_response=raw,
        )

    def extract_document_skill(
        self,
        document_metadata: dict,
        source_text: str,
    ) -> tuple[DocumentSkillPayload, ProviderMetadata]:
        schema = _ollama_document_agent_skill_schema()
        prompt = (
            "あなたは研究用学習アプリの Document Agent Skill 抽出器です。\n"
            "PDF教材本文から、学習・テスト生成に再利用できる構造化JSONを作成してください。\n"
            "RAG用chunkや検索用情報ではなく、教材範囲の知識状態として保存するJSONを返してください。\n"
            "出力は必ずJSON schemaに従ってください。\n"
            f"document_metadata: {json.dumps(document_metadata, ensure_ascii=False)}\n"
            f"source_text:\n{source_text[:24000]}\n"
        )
        result = self._generate_json(prompt, schema)
        return DocumentSkillPayload.model_validate(result["parsed"]), self._adaptive_metadata(result["raw"])

    def _generate_adaptive_assessment(
        self,
        generation_type: str,
        document_skill: dict,
        question_count: int,
        used_fingerprints: list[str],
        learner_skill: dict | None = None,
        cycle_index: int | None = None,
    ) -> tuple[AssessmentPayload, ProviderMetadata]:
        schema = _ollama_adaptive_assessment_schema(question_count)
        prompt = (
            "あなたは研究用学習アプリの採点可能なMCQテスト生成器です。\n"
            "出力は必ずJSON schemaに従ってください。JSON外の説明は禁止です。\n"
            "各問題には topic, subtopic, difficulty, stem, choices, correct_answer, rubric, fingerprint を含めてください。\n"
            "fingerprint は過去 fingerprint と完全一致しない短い識別子にしてください。\n"
            f"generation_type: {generation_type}\n"
            f"cycle_index: {cycle_index}\n"
            f"question_count: {question_count}\n"
            f"used_fingerprints: {json.dumps(used_fingerprints, ensure_ascii=False)}\n"
            f"Document Agent Skill: {json.dumps(document_skill, ensure_ascii=False)}\n"
            f"Learner Agent Skill: {json.dumps(learner_skill or {}, ensure_ascii=False)}\n"
        )
        result = self._generate_json(prompt, schema)
        return AssessmentPayload.model_validate(result["parsed"]), self._adaptive_metadata(result["raw"])

    def generate_initial_test(
        self,
        document_skill: dict,
        question_count: int,
        used_fingerprints: list[str],
    ) -> tuple[AssessmentPayload, ProviderMetadata]:
        return self._generate_adaptive_assessment("initial_test", document_skill, question_count, used_fingerprints)

    def analyze_attempt_and_create_learner_skill(
        self,
        document_skill: dict,
        assessment: dict,
        attempt: dict,
        revision: int,
        previous_skill: dict | None = None,
    ) -> tuple[LearnerSkillPayload, ProviderMetadata]:
        schema = _ollama_learner_skill_schema()
        prompt = (
            "あなたは学習者のテスト結果を分析し Learner Agent Skill を更新するAIです。\n"
            "出力は必ずJSON schemaに従ってください。\n"
            f"revision: {revision}\n"
            f"previous_skill: {json.dumps(previous_skill or {}, ensure_ascii=False)}\n"
            f"Document Agent Skill: {json.dumps(document_skill, ensure_ascii=False)}\n"
            f"assessment: {json.dumps(assessment, ensure_ascii=False)}\n"
            f"attempt: {json.dumps(attempt, ensure_ascii=False)}\n"
        )
        result = self._generate_json(prompt, schema)
        payload = LearnerSkillPayload.model_validate({**result["parsed"], "revision": revision})
        return payload, self._adaptive_metadata(result["raw"])

    def generate_learning_material(
        self,
        document_skill: dict,
        learner_skill: dict,
        cycle_index: int,
    ) -> tuple[GeneratedMaterialPayload, ProviderMetadata]:
        schema = _ollama_generated_material_schema()
        prompt = (
            "あなたは弱点補強用の教科書・参考書風教材を生成するAIです。\n"
            "Document Agent Skill の範囲外には出ず、Learner Agent Skill の weak_topics を重点化してください。\n"
            "出力は必ずJSON schemaに従ってください。\n"
            f"cycle_index: {cycle_index}\n"
            f"Document Agent Skill: {json.dumps(document_skill, ensure_ascii=False)}\n"
            f"Learner Agent Skill: {json.dumps(learner_skill, ensure_ascii=False)}\n"
        )
        result = self._generate_json(prompt, schema)
        return GeneratedMaterialPayload.model_validate(result["parsed"]), self._adaptive_metadata(result["raw"])

    def generate_cycle_test(
        self,
        document_skill: dict,
        learner_skill: dict,
        cycle_index: int,
        question_count: int,
        used_fingerprints: list[str],
    ) -> tuple[AssessmentPayload, ProviderMetadata]:
        return self._generate_adaptive_assessment(
            "cycle_test",
            document_skill,
            question_count,
            used_fingerprints,
            learner_skill,
            cycle_index,
        )

    def generate_final_test(
        self,
        document_skill: dict,
        question_count: int,
        used_fingerprints: list[str],
    ) -> tuple[AssessmentPayload, ProviderMetadata]:
        return self._generate_adaptive_assessment("final_test", document_skill, question_count, used_fingerprints)

    def generate_result_summary(
        self,
        document_skill: dict,
        learner_skill_history: list[dict],
        score_summary: dict,
    ) -> tuple[ResultSummaryPayload, ProviderMetadata]:
        schema = _ollama_result_summary_schema()
        prompt = (
            "あなたは研究用学習実験の結果を簡潔に総評するAIです。\n"
            "出力は必ずJSON schemaに従ってください。\n"
            f"Document Agent Skill: {json.dumps(document_skill, ensure_ascii=False)}\n"
            f"Learner Skill history: {json.dumps(learner_skill_history, ensure_ascii=False)}\n"
            f"score_summary: {json.dumps(score_summary, ensure_ascii=False)}\n"
        )
        result = self._generate_json(prompt, schema)
        return ResultSummaryPayload.model_validate(result["parsed"]), self._adaptive_metadata(result["raw"])


def _document_skill_prompt(document_metadata: dict, source_unit: dict, previous_document_skill: dict) -> str:
    return (
        "You are extracting reusable Document Agent Skills from a learning material.\n"
        "Return only JSON matching the schema. Do not include markdown or commentary outside JSON.\n"
        "Extract durable facts, definitions, procedures, examples, warnings, and source quotes.\n"
        "Do not infer beyond the source unit. Preserve page numbers when provided.\n"
        f"Document metadata JSON: {json.dumps(document_metadata, ensure_ascii=False)}\n"
        f"Previous Document Skill JSON: {json.dumps(previous_document_skill, ensure_ascii=False)}\n"
        f"Source unit JSON: {json.dumps(source_unit, ensure_ascii=False)}\n"
    )


def _document_skill_context_excerpt(document_skill_context: dict, *, max_chars: int = 900) -> str:
    lines: list[str] = []
    for document in document_skill_context.get("documents", []):
        filename = document.get("filename", "uploaded material")
        for entry in document.get("entries", []):
            title = entry.get("title") or entry.get("entry_type") or "entry"
            content = str(entry.get("content", "")).strip()
            if content:
                lines.append(f"- {filename}: {title}: {content}")
    excerpt = "\n".join(lines).strip()
    return excerpt[:max_chars] if excerpt else "アップロード教材の抽出済み要点がありません。"


def _study_assessment_prompt(
    assessment_type: str,
    cycle_index: int | None,
    material_text: str | None,
    document_skill_context: dict,
    skill_profile: dict,
    skills_enabled: bool,
) -> str:
    if assessment_type == "pre_test":
        purpose = "アップロード教材全体の基礎理解を測る初回テスト"
    elif assessment_type == "post_test":
        purpose = "アップロード教材全体の理解到達度を測る最終テスト"
    else:
        purpose = f"Cycle {cycle_index} の教材本文に基づくミニテスト"
    return (
        "あなたは学習支援システムのMCQテストを生成するAIです。\n"
        "出力は必ずJSONで、指定スキーマに従ってください。Markdownや説明文はJSON外に書かないでください。\n"
        "各設問はアップロード教材または提示教材の内容から作り、一般論だけの問題にしないでください。\n"
        "correct_choice_index は0始まりで、必ず正解の選択肢を指してください。\n"
        f"テスト種別: {assessment_type}\n"
        f"目的: {purpose}\n"
        f"cycle_index: {cycle_index}\n"
        f"スキル適用の有無: {skills_enabled}\n"
        f"学習者スキル（JSON）: {json.dumps(skill_profile, ensure_ascii=False)}\n"
        f"提示教材本文: {material_text or ''}\n"
        f"アップロード教材のDocument Skill（JSON）: {json.dumps(document_skill_context, ensure_ascii=False)}\n"
        "2問のMCQを生成してください。choicesは4択にしてください。"
    )


def _gemini_assessment_schema() -> dict[str, Any]:
    return {
        "type": "OBJECT",
        "properties": {
            "questions": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "question_id": {"type": "STRING"},
                        "stem": {"type": "STRING"},
                        "choices": {"type": "ARRAY", "items": {"type": "STRING"}},
                        "correct_choice_index": {"type": "INTEGER"},
                    },
                    "required": ["question_id", "stem", "choices", "correct_choice_index"],
                },
            }
        },
        "required": ["questions"],
    }


def _ollama_assessment_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "minItems": 2,
                "maxItems": 2,
                "items": {
                    "type": "object",
                    "properties": {
                        "question_id": {"type": "string"},
                        "stem": {"type": "string"},
                        "choices": {"type": "array", "minItems": 4, "maxItems": 4, "items": {"type": "string"}},
                        "correct_choice_index": {"type": "integer"},
                    },
                    "required": ["question_id", "stem", "choices", "correct_choice_index"],
                },
            }
        },
        "required": ["questions"],
    }


def _gemini_document_skill_delta_schema() -> dict[str, Any]:
    array_string = {"type": "ARRAY", "items": {"type": "STRING"}}
    pages = {"type": "ARRAY", "items": {"type": "INTEGER"}}
    return {
        "type": "OBJECT",
        "properties": {
            "document_title": {"type": "STRING"},
            "summary": {"type": "STRING"},
            "learning_objectives": array_string,
            "key_concepts": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "name": {"type": "STRING"},
                        "explanation": {"type": "STRING"},
                        "source_pages": pages,
                    },
                    "required": ["name", "explanation", "source_pages"],
                },
            },
            "definitions": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "term": {"type": "STRING"},
                        "definition": {"type": "STRING"},
                        "source_pages": pages,
                    },
                    "required": ["term", "definition", "source_pages"],
                },
            },
            "facts": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {"statement": {"type": "STRING"}, "source_pages": pages},
                    "required": ["statement", "source_pages"],
                },
            },
            "procedures": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {"title": {"type": "STRING"}, "steps": array_string, "source_pages": pages},
                    "required": ["title", "steps", "source_pages"],
                },
            },
            "examples": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {"title": {"type": "STRING"}, "content": {"type": "STRING"}, "source_pages": pages},
                    "required": ["title", "content", "source_pages"],
                },
            },
            "formulas": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "name": {"type": "STRING"},
                        "expression": {"type": "STRING"},
                        "explanation": {"type": "STRING"},
                        "source_pages": pages,
                    },
                    "required": ["name", "expression", "explanation", "source_pages"],
                },
            },
            "warnings": array_string,
            "common_misconceptions": array_string,
            "answering_guidelines": array_string,
            "source_map": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "excerpt": {"type": "STRING"},
                        "page": {"type": "INTEGER"},
                        "source_span": {"type": "STRING"},
                    },
                    "required": ["excerpt"],
                },
            },
        },
        "required": [
            "document_title",
            "summary",
            "learning_objectives",
            "key_concepts",
            "definitions",
            "facts",
            "procedures",
            "examples",
            "formulas",
            "warnings",
            "common_misconceptions",
            "answering_guidelines",
            "source_map",
        ],
    }


def _ollama_document_skill_delta_schema() -> dict[str, Any]:
    schema = _gemini_document_skill_delta_schema()
    return _lower_schema_types(schema)


def _ollama_document_agent_skill_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "learning_objectives": {"type": "array", "items": {"type": "string"}},
            "topic_map": {"type": "array", "items": {"type": "object"}},
            "concept_definitions": {"type": "array", "items": {"type": "object"}},
            "prerequisite_concepts": {"type": "array", "items": {"type": "string"}},
            "examples": {"type": "array", "items": {"type": "object"}},
            "common_misconceptions": {"type": "array", "items": {"type": "string"}},
            "difficulty_map": {"type": "array", "items": {"type": "object"}},
            "assessment_blueprint": {"type": "array", "items": {"type": "object"}},
            "canonical_explanations": {"type": "array", "items": {"type": "object"}},
            "out_of_scope": {"type": "array", "items": {"type": "string"}},
            "source_pdf_metadata": {"type": "object"},
            "revision": {"type": "integer"},
        },
        "required": [
            "learning_objectives",
            "topic_map",
            "concept_definitions",
            "prerequisite_concepts",
            "examples",
            "common_misconceptions",
            "difficulty_map",
            "assessment_blueprint",
            "canonical_explanations",
            "out_of_scope",
            "source_pdf_metadata",
            "revision",
        ],
    }


def _ollama_adaptive_assessment_schema(question_count: int) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "questions": {
                "type": "array",
                "minItems": question_count,
                "maxItems": question_count,
                "items": {
                    "type": "object",
                    "properties": {
                        "question_id": {"type": "string"},
                        "topic": {"type": "string"},
                        "subtopic": {"type": "string"},
                        "difficulty": {"type": "string", "enum": ["basic", "standard", "advanced"]},
                        "stem": {"type": "string"},
                        "choices": {"type": "array", "minItems": 2, "items": {"type": "string"}},
                        "correct_answer": {"type": "string"},
                        "rubric": {"type": "string"},
                        "fingerprint": {"type": "string"},
                    },
                    "required": [
                        "question_id",
                        "topic",
                        "difficulty",
                        "stem",
                        "choices",
                        "correct_answer",
                        "rubric",
                        "fingerprint",
                    ],
                },
            },
            "blueprint": {"type": "object"},
        },
        "required": ["title", "questions"],
    }


def _ollama_learner_skill_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "overall_mastery": {"type": "number"},
            "mastery_by_topic": {"type": "object"},
            "known_topics": {"type": "array", "items": {"type": "string"}},
            "weak_topics": {"type": "array", "items": {"type": "string"}},
            "common_mistakes": {"type": "array", "items": {"type": "string"}},
            "misconception_hypotheses": {"type": "array", "items": {"type": "string"}},
            "recommended_next_focus": {"type": "array", "items": {"type": "string"}},
            "recommended_difficulty": {"type": "string"},
            "generated_material_history_summary": {"type": "array", "items": {"type": "string"}},
            "used_question_fingerprints": {"type": "array", "items": {"type": "string"}},
            "evidence_from_attempts": {"type": "array", "items": {"type": "object"}},
            "revision": {"type": "integer"},
        },
        "required": [
            "overall_mastery",
            "mastery_by_topic",
            "known_topics",
            "weak_topics",
            "common_mistakes",
            "misconception_hypotheses",
            "recommended_next_focus",
            "recommended_difficulty",
            "generated_material_history_summary",
            "used_question_fingerprints",
            "evidence_from_attempts",
        ],
    }


def _ollama_generated_material_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "learning_goals": {"type": "array", "items": {"type": "string"}},
            "body": {"type": "string"},
            "examples": {"type": "array", "items": {"type": "string"}},
            "common_mistakes": {"type": "array", "items": {"type": "string"}},
            "checkpoints": {"type": "array", "items": {"type": "string"}},
            "target_topics": {"type": "array", "items": {"type": "string"}},
            "difficulty": {"type": "string"},
        },
        "required": ["title", "learning_goals", "body", "examples", "common_mistakes", "checkpoints", "target_topics", "difficulty"],
    }


def _ollama_result_summary_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "ai_summary": {"type": "string"},
            "improved_topics": {"type": "array", "items": {"type": "string"}},
            "remaining_weak_topics": {"type": "array", "items": {"type": "string"}},
            "misconception_reduction": {"type": "object"},
        },
        "required": ["ai_summary", "improved_topics", "remaining_weak_topics", "misconception_reduction"],
    }


def _lower_schema_types(value: Any) -> Any:
    if isinstance(value, dict):
        lowered: dict[str, Any] = {}
        for key, item in value.items():
            if key == "type" and isinstance(item, str):
                lowered[key] = item.lower()
            else:
                lowered[key] = _lower_schema_types(item)
        return lowered
    if isinstance(value, list):
        return [_lower_schema_types(item) for item in value]
    return value


def get_generation_provider(settings: Settings | None = None) -> GenerationProvider:
    active_settings = settings or get_settings()
    provider_name = active_settings.active_generation_provider
    if provider_name == "mock":
        return MockGenerationProvider(active_settings)
    if provider_name == "gemini":
        return GeminiGenerationProvider(active_settings)
    if provider_name == "ollama":
        return OllamaGenerationProvider(active_settings)
    raise ValueError(f"Unsupported generation provider: {provider_name}")


def get_generation_model_name(settings: Settings, provider_name: str | None = None) -> str:
    active_provider = provider_name or settings.active_generation_provider
    if active_provider == "gemini":
        return settings.gemini_model_generate
    if active_provider == "ollama":
        return settings.ollama_model_generate
    if active_provider == "mock":
        return "mock-model"
    return "unknown"


LLMProvider = GenerationProvider
MockProvider = MockGenerationProvider
GeminiProvider = GeminiGenerationProvider
OllamaProvider = OllamaGenerationProvider
get_provider = get_generation_provider
