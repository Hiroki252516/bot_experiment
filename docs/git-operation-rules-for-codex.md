# Gitに関する運用ルール

このドキュメントは、AI駆動開発においてCodexなどのAIコーディングエージェントがGit操作を行うためのルールです。

Codexは、コード編集だけでなく、ブランチ作成、commit、push、Pull Request作成、Pull Request確認、必要に応じたmergeまでを、このルールに従って実行してください。

---

## 1. 基本方針

- `main` ブランチは常に安定した最新版として扱う。
- `main` に直接pushしてはいけない。
- すべての作業は `main` から作成した作業ブランチで行う。
- 作業ブランチは、機能追加・修正・ドキュメント更新など、作業単位ごとに分ける。
- 作業完了後は、作業ブランチをGitHubへpushし、`main` に対してPull Requestを作成する。
- `main` への反映はPull Request経由で行う。
- 他のメンバーの変更が `main` に取り込まれている可能性があるため、作業前には必ず最新の `main` を取得する。
- 作業前後には必ず `git status` で状態を確認する。

---

## 2. 使用するコマンド

Git操作には `git` コマンドを使用する。

GitHub上のPull Request作成・確認・マージには `gh` コマンドを使用する。

作業前に、以下のコマンドでGitHub CLIにログイン済みか確認する。

```bash
gh auth status
```

未ログインの場合は、以下を実行する。

```bash
gh auth login
```

---

## 3. 禁止事項

Codexは以下の操作を実行してはいけない。

```bash
git push origin main
```

```bash
git push --force
```

```bash
git push -f
```

```bash
git reset --hard
```

```bash
git clean -fd
```

```bash
git branch -D main
```

```bash
git switch main
git commit
```

また、以下も禁止する。

- `main` ブランチで直接コード編集すること。
- `main` ブランチでcommitすること。
- `main` ブランチへ直接pushすること。
- 他人の作業ブランチを勝手に削除すること。
- 未確認のままforce pushすること。
- `.env`、秘密鍵、APIキー、パスワード、アクセストークンなどの機密情報をcommitすること。
- ユーザーやチームメンバーの未commit変更を勝手に消すこと。

---

## 4. ブランチ命名ルール

作業ブランチ名は、作業内容が分かる名前にする。

### ブランチ名の例

```text
feature/login-page
feature/user-profile
feature/payment-api
fix/login-validation
fix/header-layout
docs/update-readme
refactor/user-service
chore/update-dependencies
```

### 命名ルール

```text
feature/機能名
fix/修正内容
docs/ドキュメント内容
refactor/リファクタ内容
chore/作業内容
```

---

## 5. 作業開始時の共通ルール

Codexは、作業を始める前に必ず現在のブランチと作業状態を確認する。

```bash
git status
git branch --show-current
```

作業中の未commit変更がある場合は、勝手に上書き・削除してはいけない。

未commit変更が存在する場合は、以下を確認する。

```bash
git diff
```

その変更が今回の作業に関係ない場合は、ユーザーに確認するまで変更してはいけない。

---

## 6. 初めて作業する際のコマンド

新しい作業を開始し、`main` から新しい作業ブランチを作成する場合は、以下の手順で実行する。

```bash
# 現在の状態を確認
git status

# mainブランチに移動
git switch main

# GitHub上のmainの最新内容を取得
git pull origin main

# 作業ブランチを作成して移動
git switch -c ブランチ名
```

### 例

```bash
git status
git switch main
git pull origin main
git switch -c feature/login-page
```

---

## 7. 毎回作業する前に実行するコマンド

すでに作業ブランチが存在していて、作業を再開する場合は、以下の手順で実行する。

```bash
# 現在の状態を確認
git status

# mainブランチに移動
git switch main

# GitHub上のmainの最新内容を取得
git pull origin main

# 自分の作業ブランチに移動
git switch ブランチ名

# 最新のmainを自分の作業ブランチに取り込む
git merge main
```

### 例

```bash
git status
git switch main
git pull origin main
git switch feature/login-page
git merge main
```

### 補足

新しくブランチを作成した直後は、すでに最新の `main` からブランチを切っているため、直後に `git merge main` を実行する必要はない。

ただし、作業を再開する場合や、他のメンバーのPull Requestが `main` にマージされた後は、最新の `main` を自分の作業ブランチへ取り込むこと。

---

## 8. コード編集後に実行するコマンド

コード編集が完了したら、以下の手順で変更内容を確認し、commitする。

```bash
# 変更内容を確認
git status

# 差分を確認
git diff

# 変更ファイルをステージング
git add .

# commitする
git commit -m "変更内容を分かりやすく書く"
```

### 例

```bash
git status
git diff
git add .
git commit -m "ログイン画面を追加"
```

---

## 9. pushするコマンド

commit後、作業ブランチをGitHubへpushする。

初回pushの場合は以下を使う。

```bash
git push -u origin ブランチ名
```

### 例

```bash
git push -u origin feature/login-page
```

2回目以降、すでにupstreamが設定されている場合は以下でよい。

```bash
git push
```

---

## 10. Pull Requestを作成するコマンド

push後、GitHub CLIを使ってPull Requestを作成する。

```bash
gh pr create --base main --head ブランチ名 --title "PRタイトル" --body "PRの説明"
```

### 例

```bash
gh pr create \
  --base main \
  --head feature/login-page \
  --title "ログイン画面を追加" \
  --body "ログイン画面、入力フォーム、バリデーション処理を追加しました。"
```

PR本文には以下を含める。

```markdown
## 概要
このPull Requestで行った変更の概要を書く。

## 変更内容
- 変更点1
- 変更点2
- 変更点3

## 確認方法
1. アプリを起動する
2. 対象画面にアクセスする
3. 想定通りに動作することを確認する

## 注意点
レビュー時に注意してほしい点があれば書く。

## 関連Issue
Close #番号
```

---

## 11. Pull Request確認コマンド

Pull Request作成後、以下のコマンドで状態を確認する。

```bash
# 現在のブランチに紐づくPRを確認
gh pr view
```

```bash
# PRの差分を確認
gh pr diff
```

```bash
# CIやテストの状態を確認
gh pr checks
```

ブラウザでPRを開く場合は以下を使う。

```bash
gh pr view --web
```

---

## 12. Pull Requestを更新する場合

レビュー指摘や追加修正がある場合は、同じ作業ブランチで修正し、追加commitしてpushする。

```bash
git status
git diff
git add .
git commit -m "レビュー指摘を反映"
git push
```

pushすると、既存のPull Requestに自動的に変更が反映される。

---

## 13. mainにマージするコマンド

Pull Requestのレビュー・確認・CIが完了し、問題がない場合のみ、以下のコマンドで `main` にマージする。

基本的には、履歴を分かりやすくするために `squash merge` を使用する。

```bash
gh pr merge --squash --delete-branch
```

通常のmerge commitでマージする必要がある場合のみ、以下を使用する。

```bash
gh pr merge --merge --delete-branch
```

マージ後、ローカルの `main` を最新化する。

```bash
git switch main
git pull origin main
```

不要になったローカルブランチが残っている場合は削除する。

```bash
git branch -d ブランチ名
```

### 例

```bash
gh pr merge --squash --delete-branch
git switch main
git pull origin main
git branch -d feature/login-page
```

---

## 14. コンフリクトが発生した場合

`git merge main` 実行時にコンフリクトが発生した場合、Codexは以下の手順で対応する。

```bash
# コンフリクト状況を確認
git status
```

コンフリクトしているファイルを確認する。

```bash
git diff
```

コンフリクトしているファイルを修正する。

修正後、以下を実行する。

```bash
git add .
git commit -m "mainの変更を取り込み、コンフリクトを解消"
git push
```

コンフリクト解消後、Pull Requestの状態を確認する。

```bash
gh pr checks
gh pr diff
```

---

## 15. 作業完了時の最終確認

Codexは作業完了前に以下を確認する。

```bash
git status
```

作業ブランチに未commitの変更が残っていないことを確認する。

```bash
gh pr view
```

Pull Requestが作成されていることを確認する。

```bash
gh pr checks
```

CIやテストがある場合は、結果を確認する。

---

## 16. Codexへの実行指示

CodexはGit操作を行う際、必ず以下の順序に従う。

### 新規作業の場合

```bash
git status
git switch main
git pull origin main
git switch -c ブランチ名
```

その後、コードを編集する。

編集後は以下を実行する。

```bash
git status
git diff
git add .
git commit -m "変更内容を分かりやすく書く"
git push -u origin ブランチ名
gh pr create --base main --head ブランチ名 --title "PRタイトル" --body "PRの説明"
```

---

### 既存ブランチで作業を再開する場合

```bash
git status
git switch main
git pull origin main
git switch ブランチ名
git merge main
```

その後、コードを編集する。

編集後は以下を実行する。

```bash
git status
git diff
git add .
git commit -m "変更内容を分かりやすく書く"
git push
```

Pull Requestがまだ存在しない場合は作成する。

```bash
gh pr create --base main --head ブランチ名 --title "PRタイトル" --body "PRの説明"
```

すでにPull Requestが存在する場合は、以下で状態を確認する。

```bash
gh pr view
gh pr checks
```

---

## 17. 自動マージについて

Codexは、以下の条件をすべて満たす場合のみPull Requestをマージしてよい。

- 作業が完了している。
- Pull Requestが作成されている。
- レビューが必要な場合、承認済みである。
- CIやテストがある場合、すべて成功している。
- コンフリクトがない。
- `main` への直接pushではなく、Pull Request経由である。

条件を満たす場合は、以下を実行する。

```bash
gh pr merge --squash --delete-branch
```

その後、ローカルの `main` を最新化する。

```bash
git switch main
git pull origin main
```

---

## 18. コミットメッセージのルール

commitメッセージは、何を変更したか分かる内容にする。

### 良い例

```text
ログイン画面を追加
ユーザープロフィール編集機能を追加
ログイン時のバリデーションを修正
READMEにセットアップ手順を追加
```

### 悪い例

```text
修正
変更
test
作業
update
```

---

## 19. Pull Requestタイトルのルール

Pull Requestのタイトルは、変更内容が分かるようにする。

### 良い例

```text
ログイン画面を追加
ユーザープロフィール編集機能を追加
決済API連携処理を追加
ヘッダーのレイアウト崩れを修正
```

---

## 20. Pull Request本文テンプレート

```markdown
## 概要
<!-- このPRで何をしたかを書く -->

## 変更内容
- 
- 
- 

## 確認方法
1. 
2. 
3. 

## 注意点
<!-- レビュー時に見てほしい点があれば書く -->

## 関連Issue
<!-- 例: Close #12 -->
```

---

## 21. 推奨するGitHub側の設定

Codex側のルールだけでなく、GitHub側でも `main` ブランチを保護すること。

推奨設定は以下。

- `main` への直接pushを禁止する。
- Pull Request経由のマージを必須にする。
- 1人以上のレビュー承認を必須にする。
- CIやテストのステータスチェック成功を必須にする。
- force pushを禁止する。
- マージ前に会話の解決を必須にする。

---

## 22. 最重要ルール

- `main` に直接pushしてはいけない。
- 必ず作業ブランチで開発する。
- 必ずPull Requestを作成する。
- `main` への反映はPull Request経由で行う。
- 作業前に必ず最新の `main` を取り込む。
- 作業後に必ずcommit・push・Pull Request作成を行う。
- 機密情報をcommitしてはいけない。
- 危険なGit操作を行う前には、必ずユーザーに確認する。

---

## 23. 参考資料

- OpenAI Codex: Custom instructions with AGENTS.md  
  https://developers.openai.com/codex/guides/agents-md

- GitHub CLI manual: gh pr create  
  https://cli.github.com/manual/gh_pr_create

- GitHub CLI manual: gh pr merge  
  https://cli.github.com/manual/gh_pr_merge

- GitHub Docs: GitHub Flow  
  https://docs.github.com/get-started/quickstart/github-flow

- GitHub Docs: Branch protection rules  
  https://docs.github.com/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
