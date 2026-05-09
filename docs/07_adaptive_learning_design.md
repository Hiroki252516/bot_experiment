# 07 Adaptive Learning Design（研究仕様の正本）

本書は、本プロジェクトの研究フロー・A/B/C 条件・チャット制約・ログ仕様を確定する「機能変更の設計書」である。
既存の `docs/01_prd.md`, `docs/02_architecture.md`, `docs/03_api_db.md`, `docs/05_evaluation_protocol.md` は本書を参照し、必要な要点を抜粋して整合させる。

---

## 1. 研究目的・仮説
- 仮説：**学習ログに基づく適応型チャットボット（Group A: Skillsあり）は、非適応型（Group B: Skillsなし）より学習効果を向上させる。**
- 学習効果は主に Pre-test と Post-test の得点差（gain）で評価する。
- RAG/ベクトル検索の優劣比較は主題にしない。

---

## 2. 実験群（A/B/C）の定義

### Group A（Skillsあり / 適応型）
- 学習ログ（質問・回答・教材閲覧・MCQ結果・所要時間など）を DB に保存する。
- 学習ログから `skill_profile`（テキスト/JSON）を更新し、次の生成に反映する。
  - 次教材生成（テキスト）
  - 次ミニテスト生成（MCQ）
  - 教材閲覧中の質問への回答（読解支援チャット）

### Group B（Skillsなし / 非適応型）
- 学習ログ（質問・回答ログ含む）は **Aと同等に保存**する（分析のため）。
- ただし `skill_profile` は **参照しない・更新しない**（=プロンプトへ入れない）。
- 生成は「その場の入力（教材本文+ユーザー質問等）」のみで行う。

### Group C（書籍学習 / 対照）
- 教材形式：**テキスト**（固定教材）。
- フロー：**A/Bと同一**（Pre-test→教材→ミニテスト→推定→次教材…→Post-test）。ミニテストも挟む。
- チャット：原則なし（読解支援チャットによる介入を持たない条件として扱う）。

---

## 3. 学習フロー（確定）

### 3.1 全体フロー（A/B/C 共通の進行）
1. ログイン（簡易 user_id でも可）
2. **初回テスト（MCQ / Pre-test）**
3. **AIが理解度に合う教材（テキスト）生成**（A/B） / **固定教材提示**（C）
4. ユーザーが熟読
5. **「ミニテスト開始」**
6. **ミニテスト生成（MCQ）→ 回答 → 自動採点**
7. **理解度推定**
8. **次教材生成/提示**
9. 3〜8 を **3回反復（Cycle 1〜3）**
10. **最終テスト（MCQ / Post-test）**

### 3.2 回数・制限時間
- 反復回数は **とりあえず 3 回**（`cycle_count=3`）。
- 教材・テストとも **制限時間を設けない**（強制終了なし）。
- ただし、**教材閲覧時間・テスト所要時間は必ずログとして保存**する。

---

## 4. チャット機能（教材閲覧中のみ）

### 4.1 チャット可能タイミング（研究の制約）
- **教材閲覧中のみチャット可能**（読解支援用途に限定）。
- Pre-test / Mini-test 解答中 / Post-test 解答中はチャット不可（介入を制限）。

### 4.2 A/B の差分（厳密定義）
#### Group A（Skillsあり）
- 入力（概念）:
  - 教材本文
  - ユーザー質問
  - 直近の学習ログ要約（必要最小限）
  - **`skill_profile`（最新版）**
- 出力:
  - 読解支援の回答（教材の範囲に寄せる）
- 学習ログとして保存し、**次の教材/ミニテスト/質問回答に反映**する。

#### Group B（Skillsなし）
- 入力:
  - 教材本文
  - ユーザー質問
  - （任意）直近ログ要約は入れてもよいが、**`skill_profile` は入れない**
- 出力:
  - 読解支援の回答
- ログは保存するが、**適応（更新・参照・反映）はしない**。

---

## 5. 教材閲覧「読了」判定（確定）
- 読了判定は **ボタン操作のみ**（最低閲覧時間などの制約は設けない）。
- ただし以下は必須ログとする:
  - presented_at（教材提示時刻）
  - read_confirmed_at（読了ボタン押下時刻）
  - read_duration_seconds（差分）

---

## 6. 学習ログ（Learning Log）仕様（教材・テスト時間を含む）

### 6.1 必須ログ（A/B/C共通）
#### run（実験1回）
- run_id, user_id
- group（A|B|C）, skills_enabled
- cycle_count（=3）
- started_at, finished_at
- provider/model/prompt_version/temperature 等の再現性メタ情報

#### 教材（Cycle 1..3）
- material_id, run_id, cycle_index
- source_type（generated|fixed）
- content_text（教材本文）
- presented_at, read_confirmed_at, read_duration_seconds

#### テスト（Pre/Mini/Post）
テスト定義:
- assessment_id, run_id
- assessment_type（pre_test|mini_test|post_test）
- cycle_index（miniのみ）
- questions（JSON: stem/choices/correct）

テスト試行（attempt）:
- assessment_attempt_id, assessment_id, run_id
- started_at, submitted_at, duration_seconds
- answers（JSON）, score/max_score, per_question_correct（JSON）

#### 理解度推定
- mastery_estimate_id, run_id, cycle_index
- mastery_estimate, confidence, evidence_summary

### 6.2 チャットログ（A/Bのみ）
- chat_turn_id, run_id, material_id, cycle_index
- question_text, answer_text
- created_at

### 6.3 Skills ログ（Aのみ）
- skills（active_revision）
- skill_revisions（profile_json, update_reason, created_at）

---

## 7. `skill_profile`（テキスト/JSON）の位置づけ
- Skills はベクトル必須ではない。本研究では `skill_profile` を **テキスト/JSON（DB保存）**として扱う。
- Aのみ更新・参照・反映し、B/Cでは無効（参照/更新なし）。

最低限のフィールド例（MVP）:
- mastery（0.0〜1.0）
- known_topics / weak_topics
- common_mistakes
- recommended_difficulty
- version / updated_at

---

## 8. 評価指標（最小）
- 主指標: gain（Post - Pre）を A/B/C で群比較
- 補助: Cycle 1..3 の推移、教材閲覧時間、テスト所要時間、（A/Bのみ）チャット介入量

---

## 9. 既存 docs への反映方針（整合ルール）
- `docs/01_prd.md`: 研究目的/範囲/成功条件を本書に合わせる
- `docs/02_architecture.md`: 研究フロー中心に責務を再配置（RAG主題から外す注記）
- `docs/03_api_db.md`: run/material/assessment/mastery/chat の API と DB、時間ログ必須を明記
- `docs/05_evaluation_protocol.md`: A/B/C、Pre/Post差、時間ログ、必要CSVを更新
