# GitHubへのプッシュ方法

現在、認証が必要な状態です。以下のいずれかの方法でプッシュしてください：

## 方法1: Personal Access Token (推奨)

1. GitHubで個人アクセストークンを作成:
   - https://github.com/settings/tokens/new にアクセス
   - Note: "crypto-bot push"
   - Expiration: お好みで
   - Select scopes: `repo` にチェック
   - 「Generate token」をクリック
   - トークンをコピー（一度しか表示されません！）

2. プッシュ:
   ```bash
   git push -u origin main
   ```
   - Username: koishichito
   - Password: コピーしたトークンを貼り付け

## 方法2: GitHub CLI

```bash
# GitHub CLIをインストール済みの場合
gh auth login
gh repo view koishichito/crypto-bot --web
```

## 方法3: SSHキー

```bash
# SSHキーがある場合
git remote set-url origin git@github.com:koishichito/crypto-bot.git
git push -u origin main
```

プッシュ後、以下のURLでGitHub Actionsの実行状況を確認できます：
https://github.com/koishichito/crypto-bot/actions