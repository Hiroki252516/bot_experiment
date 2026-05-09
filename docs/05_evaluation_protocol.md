# 05 Evaluation Protocol

## 1. 評価目的

本実験は、PDF教材に基づく学習対象について、AI が被験者の理解状態を推定し、弱点補強教材とテストを 10 サイクル生成することで、初回テストから最終テストまでの成績がどの程度向上するかを測定する。

## 2. 主指標

### Gain Score

```text
gain_score = final_score - initial_score
```

### Gain Rate

```text
gain_rate = (final_score - initial_score) / initial_max_score
```

初回テストと最終テストは同じ学習範囲を測る。ただし、同一問題の丸写しは避ける。

## 3. 補助指標

- cycle_score_trend
- mastery_by_topic_trend
- weak_topic_reduction
- misconception_reduction
- material_read_duration_seconds
- test_duration_seconds
- question_overlap_rate
- learner_skill_revision_count
- generation_validation_error_count

## 4. 実験単位

1 run は、1 被験者が 1 PDF 教材に対して行う一連の実験を表す。

1 run は以下を含む。

- initial test
- initial analysis
- Cycle 1〜10
  - generated material
  - material read
  - cycle test
  - test analysis
  - Learner Agent Skill update
- final test
- result summary

## 5. 保存ログ

### run log

- run_id
- user_id
- document_id
- document_skill_revision_id
- started_at
- finished_at
- cycle_count
- state

### assessment log

- assessment_id
- assessment_type
- cycle_index
- questions_json
- question_fingerprints_json
- provider
- model
- prompt_version
- temperature
- created_at

### attempt log

- attempt_id
- assessment_id
- started_at
- submitted_at
- duration_seconds
- answers_json
- score
- max_score
- per_question_correct_json
- analysis_json

### material log

- material_id
- cycle_index
- title
- content_markdown
- focus_topics_json
- learner_skill_revision_id
- created_at

### material read log

- material_id
- presented_at
- read_confirmed_at
- read_duration_seconds

### Learner Agent Skill log

- learner_skill_revision_id
- run_id
- revision
- source_attempt_id
- skill_json
- update_reason
- created_at

### Document Agent Skill log

- document_skill_revision_id
- document_id
- revision
- skill_json
- schema_version
- extraction_prompt_version
- created_at

## 6. 問題重複の評価

各問題に fingerprint を付与する。

fingerprint は以下をもとに生成する。

- topic_key
- tested_concept
- required_reasoning_pattern
- normalized_stem
- normalized_correct_answer

サイクルテストと最終テストでは、過去 fingerprint と一致または高類似になる問題を避ける。MVP では完全一致禁止を必須とし、近似重複検出は P1 とする。

## 7. 分析観点

### 全体成績

- initial_score と final_score の差
- 正答率の差
- 10 サイクル中の伸び方

### トピック別理解度

- 初回時点の weak_topics
- 各サイクル後の mastery_by_topic
- 最終時点で改善した topic
- 最終時点でも残った weak topic

### 学習効率

- 教材閲覧時間と score gain の関係
- テスト所要時間と正答率の関係
- サイクルを重ねるごとの所要時間変化

### 生成品質

- JSON schema validation 成功率
- 問題重複率
- 教材が weak_topics を扱っている割合
- 範囲外出題率

## 8. CSV Export

### runs.csv

- run_id
- user_id
- document_id
- started_at
- finished_at
- initial_score
- final_score
- gain_score
- gain_rate

### assessments.csv

- assessment_id
- run_id
- assessment_type
- cycle_index
- question_count
- created_at

### attempts.csv

- attempt_id
- assessment_id
- run_id
- assessment_type
- cycle_index
- score
- max_score
- duration_seconds
- submitted_at

### materials.csv

- material_id
- run_id
- cycle_index
- focus_topics
- content_length
- created_at

### material_reads.csv

- material_id
- run_id
- cycle_index
- read_duration_seconds

### learner_skill_revisions.csv

- learner_skill_revision_id
- run_id
- revision
- overall_mastery
- weak_topics
- known_topics
- recommended_next_focus
- created_at

### question_items.csv

- assessment_id
- question_id
- topic_key
- difficulty
- fingerprint
- correct_rate

### generation_logs.csv

- generation_log_id
- run_id
- generation_type
- provider
- model
- prompt_version
- validation_status
- created_at

## 9. 可視化要件

Result page では最低限以下を表示する。

- 初回テスト点数
- 最終テスト点数
- 点数差
- 正答率差
- Cycle 1〜10 の点数推移
- トピック別理解度の変化
- 改善した項目
- 残った課題

## 10. 再現性要件

- すべての LLM 呼び出しに provider/model/prompt_version/temperature を保存する。
- Document Agent Skill revision を保存する。
- Learner Agent Skill revision を保存する。
- 生成されたテスト問題と教材本文を保存する。
- 採点結果と分析結果を保存する。
- 実験後に CSV だけで主要分析を再現できるようにする。
