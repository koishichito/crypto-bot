# Crypto Bot

仮想通貨取引ボット

## 機能

- 複数の取引所対応 (CCXTライブラリ使用)
- ペーパートレーディングモード
- 環境変数による設定管理

## セットアップ

1. 依存関係のインストール:
```bash
npm install
```

2. 環境変数の設定:
```bash
cp .env.example .env
# .envファイルを編集して必要な値を設定
```

3. 実行:
```bash
npm start
```

## 開発

- `npm run dev` - 開発モード (ファイル変更監視)
- `npm test` - テスト実行

## CI/CD

このリポジトリはGitHub Actionsを使用して自動テストを実行します。
プルリクエスト時にはClaude Codeによる自動レビューも行われます。