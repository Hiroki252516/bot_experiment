from __future__ import annotations

from copy import deepcopy

from app.schemas.llm import SkillDelta


def merge_skill_profile(previous_profile: dict, delta: SkillDelta) -> dict:
    next_profile = deepcopy(previous_profile)
    prefs = delta.add_preferences

    for field_name in ("preferred_explanation_style", "preferred_structure_pattern"):
        existing = list(next_profile.get(field_name, []))
        additions = getattr(prefs, field_name)
        next_profile[field_name] = list(dict.fromkeys(existing + additions))

    for field_name in ("preferred_hint_level", "preferred_answer_length", "evidence_preference"):
        value = getattr(prefs, field_name)
        if value:
            next_profile[field_name] = value

    existing_dislikes = list(next_profile.get("disliked_patterns", []))
    next_profile["disliked_patterns"] = list(dict.fromkeys(existing_dislikes + delta.add_dislikes))
    notes = list(next_profile.get("notes", []))
    if delta.summary_rule:
        notes = list(dict.fromkeys(notes + [delta.summary_rule]))
    next_profile["notes"] = notes
    return next_profile

