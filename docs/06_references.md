# 06 References

## 1. Agent Skills

- OpenAI API Skills documentation
- OpenAI Codex Agent Skills documentation
- Agent Skills open format documentation
- Agent Skills examples / catalogs

本プロジェクトでは、Agent Skills を「実験中に LLM が参照する構造化された再利用可能な知識・手順」として扱う。実装上は、PDF 教材由来の Document Agent Skill と、被験者の学習履歴由来の Learner Agent Skill を DB に JSON revision として保存する。

## 2. PDF / Document Processing

- PDF parsing libraries
- layout-aware PDF extraction
- multimodal document understanding
- structured document extraction

PDF の runtime RAG は行わない。PDF は upload/ingestion 時に一度だけ解析し、学習目標・トピック・概念・例・誤概念・評価 blueprint に分解して Document Agent Skill として保存する。

## 3. Backend

- FastAPI
- Pydantic
- SQLAlchemy
- Alembic
- PostgreSQL

## 4. Frontend

- Next.js
- React
- TypeScript

## 5. Container / DevOps

- Docker
- Docker Compose

## 6. LLM Structured Output

- JSON schema constrained output
- prompt versioning
- generation logging
- validation / retry pattern

本プロジェクトでは、テスト生成、教材生成、理解度推定、Agent Skill 更新のすべてで JSON schema validation を必須にする。

## 7. Research Design

- pre-test / post-test design
- repeated measures design
- item-level analysis
- mastery estimation
- formative assessment

## 8. Legacy References

既存ドキュメントに含まれていた RAG、embedding、pgvector、retrieval logging に関する資料は、過去設計の参考としては残してよい。ただし、今回の実験仕様では runtime path に含めない。
