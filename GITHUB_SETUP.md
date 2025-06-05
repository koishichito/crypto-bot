# GitHub連携手順

## 1. GitHubでリポジトリを作成

1. [GitHub](https://github.com)にログイン
2. 右上の「+」アイコンをクリック → 「New repository」を選択
3. 以下の設定でリポジトリを作成:
   - Repository name: `crypto-bot`
   - Description: 「仮想通貨取引ボット」（任意）
   - Public/Private: お好みで選択
   - **重要**: 「Initialize this repository with:」のチェックはすべて外す
   - 「Create repository」をクリック

## 2. ローカルリポジトリとGitHubを接続

GitHubでリポジトリを作成後、表示される画面のURLをコピーして以下のコマンドを実行:

```bash
# GitHubリポジトリをリモートとして追加
git remote add origin https://github.com/YOUR_USERNAME/crypto-bot.git

# 初回コミット
git commit -m "Initial commit: crypto bot project setup"

# GitHubにプッシュ
git push -u origin main
```

## 3. GitHub Actionsの確認

プッシュ後、GitHubリポジトリの「Actions」タブを確認すると、自動的にワークフローが実行されます。

## 4. 個人アクセストークンの設定（必要な場合）

HTTPSでプッシュ時に認証が必要な場合:

1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. 「Generate new token」をクリック
3. 必要な権限を選択（最低限 `repo` にチェック）
4. トークンを生成してコピー
5. `git push`時のパスワードとして使用

## 5. SSH接続の設定（推奨）

より安全な接続方法:

```bash
# SSHキーが既にある場合は確認
ls -la ~/.ssh

# なければ生成
ssh-keygen -t ed25519 -C "your_email@example.com"

# 公開鍵をコピー
cat ~/.ssh/id_ed25519.pub

# GitHubの Settings → SSH and GPG keys → New SSH key に貼り付け

# リモートURLをSSHに変更
git remote set-url origin git@github.com:YOUR_USERNAME/crypto-bot.git
```

## トラブルシューティング

### プッシュできない場合
```bash
# リモートURLを確認
git remote -v

# 必要に応じて変更
git remote set-url origin 正しいURL
```

### ブランチ名が異なる場合
```bash
# 現在のブランチ名を確認
git branch

# mainに変更
git branch -m main
```