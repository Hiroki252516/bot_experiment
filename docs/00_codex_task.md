# 00 Codex Task

## 2026-05 改訂方針

本リポジトリは、PDF教材をもとに被験者の学習効果を測定する研究用 Web アプリを実装する。管理者は実験前に学習対象を解説した PDF 教材をアップロードする。被験者はログイン後、初回テストを生成・受験し、その結果から AI が知識状態を推定する。以後、AI は理解が甘い箇所を重点的に補う教材を生成し、被験者が読了後にテストを受験し、結果分析と教材生成を繰り返す。この学習ループを 10 回行った後、最終テストを実施し、初回テストからの成績向上を表示する。

本システムの教材参照・学習者状態参照・テスト履歴参照は **RAG ではなく Agent Skills** によって行う。PDF はアップロード時に Document Agent Skill として構造化し、被験者のテスト結果・理解度推定・弱点・既習項目は Learner Agent Skill として更新する。実行時にベクトル検索、embedding、pgvector、retrieval pipeline を使って根拠取得する設計は禁止する。

## 目的

PDF教材で定義された学習範囲に対して、被験者ごとの理解状態を AI が継続的に推定し、弱点を重点的に補う教材とテストを 10 サイクル生成することで、初回テストと最終テストの成績差を測定できる研究用プロトタイプを構築する。

## 必須要件

- Docker Compose でローカル起動できること。
- frontend / backend / worker / database を分離すること。
- 管理者画面から PDF 教材をアップロードできること。
- PDF アップロード時に、教材内容を Document Agent Skill として構造化・保存すること。
- 被験者がログインし、初回テストを生成できること。
- 初回テストは PDF 教材の範囲全体を対象に、習熟度を測る MCQ または短答式として生成すること。
- 初回テスト送信後、AI が被験者の理解済み領域・未理解領域・誤概念を推定すること。
- 推定結果を Learner Agent Skill として保存すること。
- AI が Learner Agent Skill と Document Agent Skill を参照し、弱点補強用の教材を生成すること。
- 被験者が教材を読み終えたら、テスト開始ボタンでサイクルテストを開始できること。
- サイクルテストは毎回新規生成し、初回テストおよび過去サイクルテストと同一問題にならないようにすること。
- テスト結果を分析し、Learner Agent Skill を更新し、次の教材生成に反映すること。
- この学習サイクルを 10 回実施すること。
- 10 回完了後、最終テストを生成・実施すること。
- 最終テスト送信後、初回テストと比較した成績向上をわかりやすく表示すること。
- 管理者が run、教材、テスト、成績推移、Agent Skill 履歴、CSV export を確認できること。

## 技術指定

- backend: Python 3.12 / FastAPI / SQLAlchemy / Alembic
- frontend: Next.js / TypeScript
- db: PostgreSQL 16
- worker: Python
- provider adapter: Gemini をデフォルトとする LLM 抽象化レイヤ
- container orchestration: Docker Compose
- PDF parser: backend/worker から呼び出す抽象インターフェースとして実装

## 非採用技術

以下は新規 runtime path では使わない。

- RAG
- embedding-based retrieval
- pgvector による類似検索
- runtime chunk search
- retrieval_logs を前提にした回答生成

既存互換のために legacy テーブルを残す場合でも、今回の実験フローでは参照しない。

## 実装対象

1. monorepo skeleton
2. Dockerfile / docker-compose.yml
3. backend API
4. frontend UI
5. DB schema / Alembic migration
6. PDF upload / ingestion
7. Document Agent Skill extraction
8. Learner Agent Skill update
9. initial test generation
10. cycle material generation
11. cycle test generation
12. final test generation
13. scoring / mastery estimation
14. improvement dashboard
15. admin dashboard
16. CSV export
17. tests
18. README

## 画面要件

### 1. Admin page

- PDF 教材アップロード
- アップロード済み教材一覧
- Document Agent Skill の確認
- 実験 run 一覧
- 被験者ごとの進捗確認
- 初回/各サイクル/最終テスト結果確認
- Learner Agent Skill 履歴確認
- CSV export

### 2. Participant login page

- 簡易 `user_id` 入力でログインできる。
- 実験対象教材が紐づいた run を開始できる。

### 3. Initial test page

- 「初回テストを生成」ボタンを表示する。
- 生成中状態を表示する。
- 生成された初回テストに回答できる。
- 送信後、自動採点・理解度推定を行う。

### 4. Generated material page

- AI が生成した教材本文を表示する。
- 被験者の弱点補強を目的とした教科書・参考書風の説明にする。
- 読了後、「テスト開始」ボタンを押せる。
- 教材提示時刻、読了時刻、閲覧時間を保存する。

### 5. Cycle test page

- Cycle 1〜10 のテストを表示する。
- 過去問題と同一にならないように生成する。
- 回答送信後、自動採点・理解度推定・Learner Agent Skill 更新を行う。

### 6. Final test page

- Cycle 10 完了後に最終テストを生成する。
- 初回テストと同じ学習範囲を測るが、同一問題の丸写しは避ける。
- 送信後に最終スコアを確定する。

### 7. Result page

- 初回テスト点数
- 最終テスト点数
- 点数差
- 正答率差
- サイクルごとの点数推移
- 理解済み項目・改善項目・残課題
- 管理者向けの詳細ログ導線

## Agent Skill 要件

### Document Agent Skill

PDF教材から以下を抽出・保存する。

- learning_objectives
- topic_map
- concept_definitions
- prerequisite_concepts
- examples
- common_misconceptions
- difficulty_map
- assessment_blueprint
- canonical_explanations
- source_pdf_metadata
- revision

### Learner Agent Skill

被験者ごと、run ごとに以下を保存・更新する。

- overall_mastery
- mastery_by_topic
- known_topics
- weak_topics
- common_mistakes
- misconception_hypotheses
- recommended_next_focus
- recommended_difficulty
- generated_material_history_summary
- used_question_fingerprints
- evidence_from_attempts
- revision
- updated_at

## API 要件

- OpenAPI が出ること。
- 入出力は Pydantic で明示すること。
- LLM の機械可読な出力は JSON schema で厳格化すること。
- 状態遷移に反する API 呼び出しは 409 を返すこと。
- すべての生成物について provider/model/prompt_version/temperature を保存すること。

## 品質要件

- 主要 API の tests を実装すること。
- PDF ingestion、test generation、skill update、state transition の単体テストを用意すること。
- backend lint / type check を通すこと。
- frontend lint を通すこと。
- README に起動方法、seed 方法、テスト方法、実験操作手順を書くこと。

## 実装姿勢

- まず 1 教材、1 被験者、10 サイクルが end-to-end で完走する MVP を優先する。
- RAG を実装しない。
- Agent Skills は DB に保存する JSON として扱い、generation 時に deterministic に context 化する。
- 実験ログの再現性を最優先する。
- UI は研究実施に必要な最小機能を優先する。

## 実装後に提示するもの

1. repo 構成
2. 実装 API 一覧
3. DB schema 概要
4. 起動手順
5. 実験実行手順
6. 未実装項目
7. 今後の改善案
