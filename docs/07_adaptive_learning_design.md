# 07 Adaptive Learning Design（研究仕様の正本）

## 1. 本書の位置づけ

本書は、本プロジェクトの研究フロー・Agent Skill 設計・ログ仕様・評価仕様を確定する正本である。`docs/00_codex_task.md`、`docs/01_prd.md`、`docs/02_architecture.md`、`docs/03_api_db.md`、`docs/04_implementation_plan.md`、`docs/05_evaluation_protocol.md` は本書に従って整合させる。

## 2. 研究目的

管理者がアップロードした PDF 教材の範囲内で、被験者が初回時点で何を理解し、何を理解していないかを AI が推定する。その推定に基づいて、弱点を重点的に補う教材とテストを 10 サイクル生成し、最終テストで初回テストからの成績向上を測定する。

## 3. 技術的中核

本研究では RAG を使わない。教材参照と学習者状態参照は Agent Skills によって行う。

- PDF 教材: Document Agent Skill に変換する。
- 被験者の理解状態: Learner Agent Skill として更新する。
- 生成時: Document Agent Skill と Learner Agent Skill を deterministic に context 化して LLM に渡す。
- 禁止: embedding retrieval、vector search、runtime chunk retrieval。

## 4. 実験前準備

1. 管理者が Web アプリの管理者画面にアクセスする。
2. 本実験で学習対象とする教材 PDF をアップロードする。
3. システムが PDF を解析し、Document Agent Skill を生成する。
4. 管理者が Document Agent Skill の ready 状態を確認する。
5. 被験者が実験を開始できる状態になる。

## 5. 実験フロー

### 5.1 全体フロー

1. 被験者ログイン
2. 初回テスト生成
3. 初回テスト受験
4. 初回テスト送信
5. AI による初回理解度推定
6. Learner Agent Skill 初期化
7. Cycle 1 教材生成
8. 被験者が教材を読む
9. Cycle 1 テスト生成
10. 被験者が Cycle 1 テストを受験・送信
11. AI が結果分析し Learner Agent Skill 更新
12. Cycle 2 教材生成
13. 以後、Cycle 10 まで繰り返す
14. 最終テスト生成
15. 最終テスト受験・送信
16. 初回テストと最終テストの比較結果を表示

### 5.2 サイクル回数

- 学習サイクルは **10 回** 固定を MVP とする。
- DB には `cycle_count` として保存し、初期値を 10 とする。
- 将来の研究拡張では変更可能にしてよいが、現行実験では 10 回を正とする。

### 5.3 制限時間

- 教材閲覧・テストに強制制限時間は設けない。
- ただし以下を必ず保存する。
  - 教材提示時刻
  - 教材読了時刻
  - 教材閲覧時間
  - テスト開始時刻
  - テスト送信時刻
  - テスト所要時間

## 6. 初回テスト

### 6.1 目的

PDF教材が扱う学習範囲全体に対して、被験者の初期習熟度を測定する。

### 6.2 生成条件

- Document Agent Skill の assessment_blueprint を使用する。
- 学習範囲全体を偏りなく覆う。
- 基礎・標準・応用の難易度を含める。
- 問題数は MVP では 20 問を初期値とする。

### 6.3 送信後処理

- 自動採点する。
- トピック別正誤を分析する。
- 理解済み領域・未理解領域・誤概念を推定する。
- Learner Agent Skill revision 1 を作成する。

## 7. 教材生成

### 7.1 目的

被験者の理解が甘い部分を重点的に補う、教科書・参考書風の教材を生成する。

### 7.2 入力

- Document Agent Skill
- 最新の Learner Agent Skill
- 直前テストの分析結果
- 過去に生成した教材の要約

### 7.3 出力

- タイトル
- 学習目標
- 本文
- 例
- 注意点
- よくある誤り
- 確認ポイント
- 次テストで測る観点

### 7.4 読了判定

被験者が「テスト開始」ボタンを押した時点で教材読了とみなす。最低閲覧時間は設定しないが、閲覧時間は保存する。

## 8. サイクルテスト

### 8.1 目的

教材読了後に、被験者が対象範囲をどの程度理解したかを測定する。

### 8.2 生成条件

- Document Agent Skill の範囲内で生成する。
- 最新 Learner Agent Skill の weak_topics を重点化する。
- 初回テストおよび過去サイクルテストと完全同一の問題を出さない。
- 問題 fingerprint を生成し、重複判定に使う。
- 問題数は MVP では 10 問を初期値とする。

### 8.3 送信後処理

- 自動採点する。
- トピック別理解度を更新する。
- 誤概念を更新する。
- 次サイクルで重点化する項目を決める。
- Learner Agent Skill の新 revision を保存する。

## 9. 最終テスト

### 9.1 目的

10 サイクル後、PDF教材の学習範囲全体について最終的な習熟度を測定する。

### 9.2 生成条件

- 初回テストと同じ学習範囲を測る。
- ただし同一問題の丸写しは避ける。
- 問題数は MVP では 20 問を初期値とする。
- 初回テストとの比較が可能な blueprint にする。

### 9.3 送信後処理

- 自動採点する。
- 初回テストとの score gain を計算する。
- トピック別改善を計算する。
- 改善点・残課題を表示する。

## 10. Agent Skill 定義

### 10.1 Document Agent Skill

PDF教材を学習・生成・評価に使いやすい形に変換したもの。

```json
{
  "learning_objectives": [],
  "topic_map": [],
  "concept_definitions": [],
  "prerequisite_concepts": [],
  "examples": [],
  "common_misconceptions": [],
  "difficulty_map": [],
  "assessment_blueprint": [],
  "canonical_explanations": [],
  "out_of_scope": []
}
```

### 10.2 Learner Agent Skill

被験者の理解状態を表すもの。

```json
{
  "overall_mastery": 0.0,
  "mastery_by_topic": {},
  "known_topics": [],
  "weak_topics": [],
  "common_mistakes": [],
  "misconception_hypotheses": [],
  "recommended_next_focus": [],
  "recommended_difficulty": "basic",
  "used_question_fingerprints": [],
  "evidence_from_attempts": []
}
```

## 11. 評価指標

### 主指標

- final_score - initial_score
- final_accuracy - initial_accuracy

### 補助指標

- Cycle 1〜10 の score trend
- mastery_by_topic trend
- weak_topics の減少
- 教材閲覧時間
- テスト所要時間
- 問題重複率

## 12. 結果表示

被験者・管理者に以下を表示する。

- 初回テスト点数
- 最終テスト点数
- 点数差
- 正答率差
- サイクル別点数推移
- 改善したトピック
- まだ弱いトピック
- AI による総評

## 13. 整合ルール

- 10 サイクルを正とする。
- 教材参照は Document Agent Skill を使う。
- 学習者状態は Learner Agent Skill を使う。
- RAG は使わない。
- すべての生成・採点・分析ログを保存する。
- LLM 出力は JSON schema で検証する。
