# Codex Task

以下の仕様に従って、**研究用プロトタイプ一式**を monorepo で実装してください。

## 目的
学習者の回答選択を利用して、学習者ごとの説明好みを「Skill」として蓄積し、次回以降の回答生成に反映する学習支援チャットボットを構築する。

## 必須要件
- 開発環境は Docker コンテナを用いること
- `docker compose up --build` でローカル起動できること
- フロントエンド、バックエンド、DB、worker を分離すること
- 学習者の質問に対して **複数回答候補（初期値 3 件）** を生成すること
- ユーザーが最良と思う回答候補を選択できること
- 選択された回答・選択されなかった回答の両方を保存すること
- ユーザーごとの Skill を保存し、次回生成時に反映すること
- RAG により学習資料を検索して回答に使うこと
- 実験のために **skills 有効 / 無効** を切り替えられること
- 主観評価（満足度・わかりやすさ等）を保存できること
- 実験ログをエクスポートできること

## 技術指定
- backend: Python 3.12 / FastAPI / SQLAlchemy / Alembic
- frontend: Next.js / TypeScript
- db: PostgreSQL 16 + pgvector
- worker: Python
- provider adapter: Gemini をデフォルトとする LLM 抽象化レイヤ
- container orchestration: Docker Compose

## 実装対象
1. monorepo の作成
2. Dockerfile / docker-compose.yml
3. backend API
4. frontend UI
5. DB schema と migration
6. RAG ingestion
7. RAG retrieval
8. candidate generation
9. answer selection API
10. feedback persistence
11. skill updater
12. experiment mode
13. seed data
14. tests
15. README

## 画面要件
### 1. Chat page
- ユーザーが質問入力できる
- 候補回答を 3 件表示する
- 各回答に「これを選ぶ」ボタンを表示する
- 選択後、満足度 1–10、わかりやすさ 1–10、自由記述を送れる

### 2. Chat log page
- 会話履歴を時系列表示する
- その時の候補回答、選択結果、評価を確認できる

### 3. Admin / Experiment page
- users 一覧
- skills ON/OFF 条件
- ingest 実行
- skill history 表示
- ログ CSV export

## API 要件
- OpenAPI が出ること
- 入出力は Pydantic で明示すること
- LLM の機械可読な結果は JSON schema で厳格化すること

## RAG 要件
- 学習資料（pdf, md, txt）を投入できる
- chunking して embeddings を保存する
- top-k retrieval ができる
- 回答時に取得した文脈を candidate generation に渡す
- どの chunk を参照したかログに残す

## Skill 要件
Skill はユーザー別に持つ。内容は少なくとも以下を扱う:
- preferred_explanation_style
- preferred_structure_pattern
- preferred_hint_level
- preferred_answer_length
- disliked_patterns
- evidence_preference
- updated_at
- revision

SkillUpdater は以下を行う:
- 選択回答と非選択回答の比較
- 差分特徴の抽出
- 次回も再現可能なルールへの正規化
- 新しい skill revision の保存

## 実験要件
- 同一 user / 同一 query で skills ON/OFF を比較できる
- ランダム割り当てではなく、少なくとも明示フラグで条件を固定可能にする
- 後から比較分析しやすいよう、すべての候補と選択結果を保存する

## 品質要件
- 重要 API の tests を実装する
- backend lint / type check を通す
- frontend lint を通す
- README に初期セットアップ、起動方法、seed 方法、テスト方法を書く

## 実装姿勢
- まず MVP を end-to-end で完成させる
- 過度なマイクロサービス化はしない
- 必要な abstraction のみ導入する
- 再現性と実験ログを重視する

## 参照資料
- `docs/01_prd.md`
- `docs/02_architecture.md`
- `docs/03_api_db.md`
- `docs/04_implementation_plan.md`
- `docs/05_evaluation_protocol.md`

## 最後に
実装後は、以下を提示してください。
1. repo 構成
2. 実装した API 一覧
3. DB schema 概要
4. 起動手順
5. 未実装項目
6. 今後の改善案
