目的:
このリポジトリを、docs/ と AGENTS.md に書かれている新しい研究用 Web アプリ仕様に合わせて修正してください。

最重要:
まず必ず以下を読んでください。

- AGENTS.md
- docs/00_codex_task.md
- docs/01_prd.md
- docs/02_architecture.md
- docs/03_api_db.md
- docs/04_implementation_plan.md
- docs/05_evaluation_protocol.md
- docs/06_references.md
- docs/07_adaptive_learning_design.md
- docs/git-operation-rules-for-codex.md

仕様判断で迷った場合は、以下の優先順位で判断してください。

1. docs/07_adaptive_learning_design.md
2. docs/03_api_db.md
3. docs/02_architecture.md
4. docs/04_implementation_plan.md
5. docs/00_codex_task.md
6. AGENTS.md

もし AGENTS.md が docs/07_adaptive_learning_design.md と矛盾している場合は、docs/07_adaptive_learning_design.md を正としてください。そのうえで、必要なら AGENTS.md も docs/07 に合わせて修正してください。

今回の新仕様の要約:
このシステムは、PDF 教材をもとに被験者の学習効果を測定する研究用 Web アプリです。

実験フローは以下です。

1. 管理者が、実験前に学習対象を解説した PDF 教材をアップロードする。
2. システムは PDF を解析し、Document Agent Skill として構造化・保存する。
3. 被験者がログインする。
4. 被験者が「初回テストを生成」ボタンを押す。
5. システムは、PDF 教材の範囲全体に対する初回テストを生成する。
6. 被験者が初回テストを解き、送信する。
7. システムは初回テストを採点し、AI が被験者の理解済み領域・未理解領域・誤概念を推定する。
8. 推定結果を Learner Agent Skill として保存する。
9. システムは、Learner Agent Skill と Document Agent Skill に基づき、被験者の弱点を重点的に補う教科書・参考書風の教材を生成する。
10. 被験者は生成教材を読む。
11. 被験者が「テスト開始」ボタンを押す。
12. システムは、同じ学習対象範囲内でサイクルテストを生成する。
13. サイクルテストは、初回テストや過去のサイクルテストと完全に同一にならないようにする。
14. 被験者がサイクルテストを解き、送信する。
15. システムはテスト結果を分析し、Learner Agent Skill を更新する。
16. 更新された Learner Agent Skill に基づいて、次の弱点補強教材を生成する。
17. 9〜16 の学習サイクルを合計 10 回行う。
18. Cycle 10 完了後、最終テストを生成・実施する。
19. 最終テスト送信後、初回テストと最終テストを比較し、成績向上を分かりやすく表示する。
20. 管理者は、run、教材、テスト、成績推移、Agent Skill 履歴、CSV export を確認できる。

絶対に守ること:
この新仕様では RAG を使わないでください。

以下は新しい runtime path では禁止です。

- RAG
- embedding-based retrieval
- pgvector similarity search
- runtime chunk retrieval
- retrieval pipeline
- retrieval_logs を根拠取得や生成に使う設計
- PDF を chunk 化してベクトル検索する設計
- local sentence-transformers を新仕様の必須 component にする設計

既存互換のために legacy table や legacy module が残るのは構いませんが、今回の実験フローでは使わないでください。

Agent Skills の扱い:
このプロジェクトにおける Agent Skill は、アプリケーション内で DB に保存する versioned JSON knowledge/state object です。

- PDF 教材由来のものを Document Agent Skill とする。
- 被験者の理解状態由来のものを Learner Agent Skill とする。
- どちらも revision として保存する。
- LLM 生成時には、Document Agent Skill と Learner Agent Skill を deterministic に prompt context へ変換して使う。
- OpenAI の hosted Skills を直接使うことは必須ではない。

実装の優先順位:
まず、1 つの PDF 教材、1 人の被験者、10 サイクル、最終テスト、結果表示まで end-to-end で完走する MVP を完成させてください。

優先順位は以下です。

P0:
- Docker Compose で起動できる状態を維持する
- DB schema / Alembic migration
- PDF upload
- Document Agent Skill extraction
- participant login / run start
- initial test generation
- initial test submission / scoring
- Learner Agent Skill initial revision
- weak-topic material generation
- material read confirmation
- cycle test generation
- duplicate question fingerprint handling
- cycle test submission / scoring
- Learner Agent Skill update
- 10-cycle state machine
- final test generation
- final test submission / scoring
- result page / improvement dashboard

P1:
- admin analytics
- CSV export
- generation logs
- retry handling
- better error messages

P2:
- UI polish
- charts
- multiple PDF experiments
- richer item analysis

具体的に実装してほしいこと:

1. 現状調査
- 現在の apps/backend、apps/frontend、apps/worker、packages/shared-schemas、DB models、migrations、README を確認してください。
- 旧仕様の chat / RAG / 3候補回答選択 / skills_enabled 実験がどこにあるか確認してください。
- 既存実装を壊さずに使える部分と、新仕様に置き換えるべき部分を整理してください。

2. DB schema を新仕様に合わせる
最低限、以下の概念を保存できるようにしてください。

- users
- source_documents
- document_skill_revisions
- document_skill_entries
- experiment_runs
- generated_assessments
- assessment_items
- assessment_attempts
- generated_materials
- material_reads
- learner_skill_revisions
- generation_logs
- result_summaries
- export_jobs

既存の legacy RAG 系テーブルがある場合は、必要なら残して構いません。ただし新仕様の runtime path からは参照しないでください。

3. Document Agent Skill を実装する
- 管理者が PDF 教材をアップロードできるようにしてください。
- PDF からテキストを抽出してください。
- 抽出結果から Document Agent Skill JSON を生成してください。
- JSON schema validation を行ってください。
- revision として DB に保存してください。
- 管理者画面で Document Agent Skill の内容を確認できるようにしてください。

Document Agent Skill には最低限以下を含めてください。

- learning_objectives
- topic_map
- concept_definitions
- prerequisite_concepts
- examples
- common_misconceptions
- difficulty_map
- assessment_blueprint
- canonical_explanations
- out_of_scope
- source_pdf_metadata
- revision

4. Learner Agent Skill を実装する
- 初回テスト提出後に Learner Agent Skill revision 1 を作成してください。
- 各サイクルテスト提出後に新しい revision を保存してください。
- append-only revision を基本にしてください。
- 生成時は最新 revision を使ってください。

Learner Agent Skill には最低限以下を含めてください。

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

5. Initial Test を実装する
- 被験者が「初回テストを生成」ボタンを押せるようにしてください。
- Document Agent Skill の assessment_blueprint に基づき、教材範囲全体を測る初回テストを生成してください。
- MVP の初期値として問題数は 20 問にしてください。
- MCQ または短答式で、採点可能な形式にしてください。
- 各問題には topic、subtopic、difficulty、correct_answer、rubric を保存してください。
- 送信後に自動採点し、理解済み領域、未理解領域、誤概念を推定してください。
- 結果から Learner Agent Skill revision 1 を保存してください。

6. 弱点補強教材生成を実装する
- Document Agent Skill と最新 Learner Agent Skill を使って、弱点を重点的に補う教材を生成してください。
- 教科書・参考書のように読める本文にしてください。
- 出力には最低限以下を含めてください。
- title
- learning_goals
- body
- examples
- common_mistakes
- checkpoints
- target_topics
- difficulty
- 被験者が教材を閲覧できる UI を作ってください。
- 「テスト開始」ボタン押下時に読了とみなし、教材提示時刻、読了時刻、閲覧時間を保存してください。

7. Cycle Test を実装する
- Cycle 1〜10 の各サイクルでテストを生成してください。
- MVP の初期値として各サイクルテストは 10 問にしてください。
- 最新 Learner Agent Skill の weak_topics を重点化してください。
- ただし Document Agent Skill の範囲外には出ないようにしてください。
- 初回テストおよび過去サイクルテストと完全同一の問題を出さないでください。
- used_question_fingerprints を生成・保存・参照してください。
- テスト送信後に採点し、topic 別理解度、誤概念、次サイクル重点項目を更新してください。
- Learner Agent Skill の新 revision を保存してください。

8. 10-cycle orchestration を実装する
- cycle_count は MVP では 10 固定にしてください。
- experiment_runs に cycle_count=10 を保存してください。
- 順序外 API 呼び出しは 409 を返してください。
- Cycle 10 の submit が完了するまで final test に進ませないでください。
- 被験者画面に現在の cycle と次にやるべき action を表示してください。

9. Final Test を実装する
- Cycle 10 完了後に最終テストを生成できるようにしてください。
- 初回テストと同じ学習範囲を測ってください。
- ただし同一問題の丸写しは避けてください。
- MVP の初期値として問題数は 20 問にしてください。
- 初回テストとの比較が可能な blueprint / topic mapping を保存してください。
- 送信後に自動採点してください。

10. Result Page を実装する
被験者・管理者が以下を確認できるようにしてください。

- initial_score
- final_score
- gain_score
- gain_rate
- initial_accuracy
- final_accuracy
- accuracy_gain
- cycle_score_trend
- topic_mastery_before_after
- improved_topics
- remaining_weak_topics
- misconception_reduction
- material_read_duration_summary
- test_duration_summary
- AI による総評

初回テストから最終テストまでにどれくらい成績が向上したかを、人間が一目で確認できる UI にしてください。

11. Admin 画面を実装・修正する
管理者が以下をできるようにしてください。

- PDF 教材アップロード
- Document Agent Skill 抽出
- Document Agent Skill revision 確認
- run 一覧
- run 詳細
- 被験者の進捗確認
- initial / cycle / final test 結果確認
- Learner Agent Skill revision 確認
- generation logs 確認
- CSV export

12. CSV export を実装する
最低限、以下を export できるようにしてください。

- runs.csv
- source_documents.csv
- document_skill_revisions.csv
- document_skill_entries.csv
- generated_assessments.csv
- assessment_items.csv
- assessment_attempts.csv
- generated_materials.csv
- material_reads.csv
- learner_skill_revisions.csv
- generation_logs.csv
- result_summaries.csv

13. LLM provider abstraction を整備する
- ollamaでgemma4:e2bを動かす
- mock provider を用意し、API key なしでも end-to-end flow を確認できるようにしてください。
- すべての LLM 出力は structured JSON を基本にしてください。
- JSON schema validation を必ず行ってください。
- provider、model_name、prompt_version、temperature、input_schema_version、output_schema_version、generated_at、validation_status を generation_logs に保存してください。

14. 既存旧仕様の扱い
- 旧 chat UI、3候補生成、answer selection、RAG ingestion/retrieval、pgvector similarity search がある場合、新実験フローからは切り離してください。
- 完全削除が大きすぎる場合は legacy として残して構いません。
- ただし新仕様の participant flow / admin flow / generation path からは呼ばないでください。
- README でも legacy と新仕様を混同しないように更新してください。

15. README を更新する
README に以下を明記してください。

- プロジェクト概要
- 新しい実験フロー
- RAG を使わず Agent Skills を使うこと
- Docker 起動方法
- .env 設定
- mock provider での動作確認方法
- ollama provider の設定方法
- 管理者の操作手順
- 被験者の操作手順
- 10 サイクル完走手順
- テスト実行方法
- CSV export 方法
- legacy RAG 関連が残っている場合は、それが新 runtime path では使われないこと

16. Tests を追加・修正する
最低限、以下のテストを用意してください。

- PDF upload
- Document Agent Skill extraction
- run start
- initial test generation
- initial test submission
- initial scoring
- Learner Agent Skill creation
- weak-topic material generation
- material read confirmation
- cycle test generation
- duplicate question avoidance
- cycle test submission
- Learner Agent Skill update
- 10-cycle progression
- invalid state transition returns 409
- final test generation
- final test submission
- result summary calculation
- CSV export
- JSON schema validation

17. 実装完了条件
完了とみなす条件は以下です。

- docker compose up --build で起動する。
- 管理者が PDF 教材をアップロードできる。
- PDF から Document Agent Skill を抽出・保存できる。
- 被験者が run を開始できる。
- 被験者が初回テストを生成・回答・送信できる。
- システムが初回テストを採点できる。
- Learner Agent Skill revision 1 が作成される。
- システムが弱点補強教材を生成できる。
- 被験者が教材を読み、「テスト開始」を押せる。
- システムがサイクルテストを生成できる。
- サイクルテストが過去問題と完全重複しない。
- 被験者が Cycle 1〜10 を順番に完走できる。
- 各サイクル後に Learner Agent Skill revision が増える。
- Cycle 10 完了後に最終テストを生成・提出できる。
- 初回テストと最終テストの成績向上が表示される。
- 管理者が run、assessment、material、Agent Skill revision、generation log を確認できる。
- 管理者が CSV export できる。
- 新 runtime path で RAG / embedding retrieval / pgvector similarity search を使っていない。
- critical backend tests が通る。
- README が新仕様に更新されている。

作業の進め方:
1. まずリポジトリを確認し、現状と docs の差分を短く整理してください。
2. 実装計画を立ててください。
3. その後、優先順位 P0 から順に実装してください。
4. 一度にすべてが大きすぎる場合でも、MVP の end-to-end 完走を最優先してください。
5. 途中で旧仕様と新仕様が衝突した場合、docs/07_adaptive_learning_design.md を優先してください。
6. 実装後、実行したコマンド、テスト結果、残課題をまとめてください。


最終出力:
実装後、以下を報告してください。

1. 変更概要
2. 新しい実験フローがどこまで動くか
3. 追加・変更した API 一覧
4. 追加・変更した DB schema / migration
5. 追加・変更した frontend page
6. Agent Skill 実装の概要
7. RAG / embedding / pgvector retrieval を新 runtime path から排除した確認結果
8. 実行したテスト
9. テスト結果
10. 起動方法
11. 操作手順
12. 未実装項目
13. 次にやるべき改善案


ターミナルの操作もgit操作も全て任せます。
ちなみにこのプロンプトはpromptフォルダのcurrent.mdにおいてあります。