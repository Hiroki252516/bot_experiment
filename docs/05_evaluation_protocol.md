# 05 Evaluation Protocol（A/B/C：学習効果の群比較）

本書は `docs/07_adaptive_learning_design.md` の研究フロー（Pre → Cycle1..3 → Post）を前提に、保存ログと評価指標を定義する。

> 2026-05 update: runtime retrieval logs は legacy。教材参照の評価単位は **document_skill_usage_logs** と **document_skill_entries**。

## 1. 目的
研究仮説を検証する。
- 仮説: **学習ログに基づく適応型（Group A: Skillsあり）は、非適応型（Group B: Skillsなし）より学習効果を向上させる。**
- 追加比較: Group C（書籍学習: 固定テキスト教材、同一フローでテスト実施）との群比較を行う。

## 2. 実験条件（群定義）
- Group A: `skills_enabled=true`（skill 更新・参照・反映あり）
- Group B: `skills_enabled=false`（skill 更新・参照・反映なし。ログは保存）
- Group C: `skills_enabled=false` + `material_source=fixed`（固定教材。フローは同一。チャット介入なし）

## 3. 保存すべきログ（必須）
本研究の最重要ログは「Pre/Post」「Cycle1..3」「教材/テスト所要時間」である。時間制限は設けないが、所要時間は必ず保存する。

### 3.1 run 単位
- run_id
- user_id
- group (A|B|C)
- skills_enabled
- cycle_count（MVP=3）
- started_at / finished_at
- provider name / model name / temperature / top_p / prompt_version

<<<<<<< HEAD
### Document Skill usage 単位
- document_id
- document_skill_revision_id
- document_skill_entry_id
- entry_type
- included_order
- context_hash
=======
### 3.2 教材単位（Cycle 1..3）
- material_id
- run_id
- cycle_index
- source_type (generated|fixed)
- difficulty（A/B の生成物。C は固定でも付与可能）
- presented_at
- read_confirmed_at
- read_duration_seconds
>>>>>>> main

### 3.3 テスト定義（Pre/Mini/Post）
- assessment_id
- run_id
- assessment_type (pre_test|mini_test|post_test)
- cycle_index（miniのみ）
- questions（stem/choices/correct など、正本は JSON）

### 3.4 テスト試行（attempt）
- assessment_attempt_id
- assessment_id
- run_id
- assessment_type
- cycle_index（miniのみ）
- started_at
- submitted_at
- duration_seconds
- answers（正本は JSON）
- score / max_score
- per_question_correct（正本は JSON）

### 3.5 理解度推定（推奨）
- mastery_estimate_id
- run_id
- cycle_index
- mastery_estimate（数値）
- confidence
- evidence_summary
- created_at

### 3.6 チャット（A/Bのみ、教材閲覧中のみ）
- chat_turn_id
- run_id
- material_id
- cycle_index
- question_text
- answer_text
- created_at

### 3.7 skills（Aのみ）
- skill_id / active_revision
- skill_revisions（old/new、update_reason、profile_json）

## 4. 分析指標（最小）
### 4.1 主指標（学習効果）
- **gain = Post-test score - Pre-test score**
  - 群比較: A vs B vs C

### 4.2 補助指標（過程）
- Cycle 1..3 のミニテスト得点推移（学習曲線）
- 教材閲覧時間（read_duration_seconds）の分布と群差
- テスト所要時間（duration_seconds）の分布と群差
- チャット介入量（質問回数、文字数など）と成績との関係（A/B）

## 5. 最低限必要なエクスポート（CSV/JSONL）
MVP では CSV を必須とし、JSONL は任意だが推奨。

<<<<<<< HEAD
## 4. 実験条件
最低限:
- Condition A: skills_enabled=false
- Condition B: skills_enabled=true

## 5. 最低限必要な CSV
- turns.csv
- candidates.csv
- feedback.csv
- skill_revisions.csv
- document_skill_revisions.csv
- document_skill_entries.csv
- document_skill_usage_logs.csv
- retrievals.csv は deprecated header のみ互換維持
=======
必須 CSV:
- runs.csv
- materials.csv
- material_reads.csv
- assessments.csv
- assessment_attempts.csv
- mastery_estimates.csv（推奨だが欠損許容はしない方がよい）
- chat_turns.csv（A/Bのみ。C は空でよい）
- skill_revisions.csv（Aのみ）
>>>>>>> main

## 6. 再現性のための保存項目
- provider name
- model name
<<<<<<< HEAD
- temperature
- top_p
- candidate_count
- Document Skill extraction model
- Document Skill prompt_version
- Document Skill context budget
=======
- temperature / top_p
>>>>>>> main
- prompt_version
- cycle_count（=3）
- group / skills_enabled
- material source_type（generated|fixed）

## 7. 研究上の注意
- 時間制限は設けない（強制終了しない）。ただし所要時間は必須ログとする。
- Group B は「同一UI/同一LLMで Skills を使わない」に固定し、LLM 変更（例: Ollama 固定）を入れる場合は別条件として扱う（交絡を増やすため）。
