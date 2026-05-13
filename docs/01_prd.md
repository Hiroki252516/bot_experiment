# 01 Product Requirements Document

## 1. 概要

本プロダクトは、PDF教材をもとに被験者の学習効果を測定する研究用 Web アプリである。管理者が事前に学習対象を解説した PDF 教材をアップロードし、システムはその教材を Document Agent Skill として構造化する。被験者は初回テストを受け、その結果から AI が知識レベルを推定する。AI は推定結果を Learner Agent Skill として保存し、弱点を重点的に補う教材とテストを 10 サイクル生成する。最後に最終テストを実施し、初回テストとの成績差を表示する。

## 2. 研究目的

PDF教材で定義された学習範囲において、AI が被験者の理解済み領域・未理解領域・誤概念を継続的に推定し、それに応じた教材を生成することで、被験者の学習成果がどの程度向上するかを測定する。

## 3. 研究仮説

- H1: 初回テスト結果から Learner Agent Skill を作成し、以後の教材生成に反映することで、10 サイクル後の最終テスト成績は初回テストより向上する。
- H2: サイクルごとのテスト結果を Learner Agent Skill に反映すると、弱点領域の正答率が段階的に改善する。
- H3: RAG ではなく Agent Skills によって教材内容と学習者状態を構造化することで、生成・分析・評価ログを再現性高く管理できる。

## 4. 対象ユーザー

### 管理者

- 実験対象 PDF 教材をアップロードする。
- 被験者の進捗、スコア、理解度推定、Agent Skill 履歴を確認する。
- 実験ログを CSV export する。

### 被験者

- Web アプリにログインする。
- 初回テストを生成・受験する。
- AI が生成した教材を読む。
- 各サイクルテストを受験する。
- 最終テストを受験する。
- 自身の成績向上を確認する。

## 5. 実験フロー

1. 管理者が PDF 教材をアップロードする。
2. システムが PDF を解析し、Document Agent Skill を生成する。
3. 被験者がログインする。
4. 被験者が「初回テストを生成」ボタンを押す。
5. AI が Document Agent Skill から学習範囲全体を対象とした初回テストを生成する。
6. 被験者が初回テストを解き、送信する。
7. AI が初回テスト結果を分析し、Learner Agent Skill を作成する。
8. AI が弱点補強用の教材を生成する。
9. 被験者が教材を読む。
10. 被験者が「テスト開始」ボタンを押す。
11. AI が過去問題と重複しないサイクルテストを生成する。
12. 被験者がサイクルテストを解き、送信する。
13. AI が結果を分析し、Learner Agent Skill を更新する。
14. 8〜13 を 10 回繰り返す。
15. AI が最終テストを生成する。
16. 被験者が最終テストを解き、送信する。
17. システムが初回テストと最終テストの成績差を表示する。

## 6. MVP スコープ

- PDF 教材 1 件のアップロード
- Document Agent Skill extraction
- 被験者ログイン
- run 開始
- 初回テスト生成・提出・採点
- Learner Agent Skill 作成
- 教材生成
- 10 回のサイクルテスト生成・提出・採点
- Learner Agent Skill 更新
- 最終テスト生成・提出・採点
- 成績向上表示
- 管理者用ログ確認
- CSV export

## 7. 非スコープ

- 本格的な認証基盤
- 複数教材を横断する実験
- RAG / embedding / vector search
- リアルタイム共同編集
- 決済機能
- LMS 連携

## 8. 成功条件

- 管理者が PDF をアップロードし、Document Agent Skill が生成される。
- 被験者が初回テストから最終テストまで完走できる。
- 10 サイクル分の教材・テスト・分析結果が保存される。
- 各テストが過去テストと完全重複しない。
- 初回テストと最終テストの点数差が UI に表示される。
- 管理者が全ログを CSV export できる。
- 新規 runtime path に RAG が含まれない。

## 9. 主要指標

- initial_score
- final_score
- gain_score = final_score - initial_score
- gain_rate
- cycle_score_trend
- mastery_by_topic_trend
- weak_topic_reduction
- material_read_duration_seconds
- test_duration_seconds
- generated_question_overlap_rate

## 10. プロダクト原則

- 研究ログの完全性を UI の見た目より優先する。
- LLM 生成結果は JSON schema で検証する。
- すべての生成・採点・推定に再現性メタデータを保存する。
- 教材参照は Document Agent Skill、学習者状態参照は Learner Agent Skill に限定する。
- RAG を使わない。
