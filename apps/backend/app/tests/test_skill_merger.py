from app.schemas.llm import SkillDelta
from app.skills.merger import merge_skill_profile


def test_merge_skill_profile_merges_lists_and_scalars() -> None:
    previous = {
        "preferred_explanation_style": ["hint-first"],
        "preferred_structure_pattern": ["steps-then-check"],
        "preferred_hint_level": "low",
        "preferred_answer_length": "short",
        "disliked_patterns": ["too-abstract"],
        "evidence_preference": "none",
        "notes": [],
    }
    delta = SkillDelta.model_validate(
        {
            "add_preferences": {
                "preferred_explanation_style": ["example-first"],
                "preferred_structure_pattern": ["example-then-steps-then-check"],
                "preferred_hint_level": "medium",
                "preferred_answer_length": "medium",
                "evidence_preference": "cite-retrieved-context",
            },
            "add_dislikes": ["answer-only"],
            "summary_rule": "Use worked examples first.",
        }
    )

    merged = merge_skill_profile(previous, delta)

    assert merged["preferred_explanation_style"] == ["hint-first", "example-first"]
    assert merged["preferred_hint_level"] == "medium"
    assert "answer-only" in merged["disliked_patterns"]
    assert "Use worked examples first." in merged["notes"]

