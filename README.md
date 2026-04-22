# Learning Skill Accumulation Chatbot — Codex Handoff

このフォルダは、研究テーマ「学習者の回答選択を用いたスキル蓄積型学習支援チャットボット」を Codex に実装してもらうためのハンドオフ資料です。

## 含まれる資料
- `AGENTS.md`  
  Codex 向けの最上位指示。まず最初に読むこと。
- `docs/00_codex_task.md`  
  Codex にそのまま渡せる実装依頼文。
- `docs/01_prd.md`  
  プロダクト要件・研究要件・成功条件。
- `docs/02_architecture.md`  
  システム構成、サービス構成、Docker 構成、主要フロー。
- `docs/03_api_db.md`  
  API 仕様、DB スキーマ、Skill 更新ロジック、JSON スキーマ。
- `docs/04_implementation_plan.md`  
  実装順序、受け入れ条件、テスト、マイルストーン。
- `docs/05_evaluation_protocol.md`  
  研究実験用のログ設計と評価計画。

## 前提
- 開発環境は Docker コンテナを使用する
- 研究プロトタイプとして、**まずはローカルで完全再現できること**を最優先にする
- LLM プロバイダは **Gemini をデフォルト**とするが、将来差し替えできるように抽象化する
- ベクトル検索は **PostgreSQL + pgvector** を採用する
- バックエンドは **Python + FastAPI**
- フロントエンドは **Next.js + TypeScript**
- 非同期処理は **worker サービス** に切り出す

## 想定する最終成果物
Codex にこのフォルダを渡して、以下を生成させる想定です。
1. Docker Compose で起動できる monorepo
2. チャット UI / 回答候補選択 UI / チャットログ閲覧 UI
3. バックエンド API
4. RAG 用データ投入と検索
5. Skills の保存・参照・更新
6. 回答候補の複数生成
7. フィードバック蓄積と SkillUpdater
8. 実験ログの保存と集計 API
9. テストと README

## 実装スコープの優先順位
1. エンドツーエンドで最低限動く MVP
2. ログと再現性
3. 実験に必要な比較条件（skills ON/OFF）
4. UI 改善
5. 研究用集計
