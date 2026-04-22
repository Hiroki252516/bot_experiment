# 05 Evaluation Protocol

## 1. 目的
研究仮説を検証するため、skills の蓄積有無が
1. ユーザーが選択する回答の予測可能性
2. 主観評価
に与える影響を比較する。

## 2. 保存すべきログ
### 会話単位
- user_id
- conversation_id
- turn_id
- timestamp
- question_text
- skills_enabled
- active_skill_revision
- model_name
- prompt_version

### retrieval 単位
- retrieved chunk ids
- similarity scores

### candidate 単位
- candidate_id
- rank
- title
- style_tags
- answer_text
- generation metadata

### feedback 単位
- selected_candidate_id
- satisfaction_score
- clarity_score
- comment

### skill update 単位
- old_revision
- new_revision
- update_reason
- diff summary

## 3. 分析指標
### 仮説1向け
- selected rank frequency
- style_tag consistency
- 次回選択と skill rule の整合度
- 予測モデルを後付けで作る場合の top-1 accuracy

### 仮説2向け
- satisfaction_score 平均
- clarity_score 平均
- 自由記述の質的分析
- skills ON/OFF の群比較

## 4. 実験条件
最低限:
- Condition A: skills_enabled=false
- Condition B: skills_enabled=true

## 5. 最低限必要な CSV
- turns.csv
- candidates.csv
- feedback.csv
- skill_revisions.csv
- retrievals.csv

## 6. 再現性のための保存項目
- provider name
- model name
- temperature
- top_p
- candidate_count
- embedding model
- chunking strategy
- retrieval top_k
- prompt_version

## 7. 研究上の注意
- 候補表示順が結果に影響する可能性があるため、将来的には順序効果を制御できるよう設計余地を残す
- まずは固定順でよいが、DB には rank を必ず保存する
- 被験者実験では匿名化しやすいよう export で display_name を除外できるようにする
