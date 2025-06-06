# Crypto Bot

仮想通貨自動取引ボット (pybotters使用)

## 🚀 機能

- **Bybit取引所対応** - pybottersライブラリを使用した高速取引
- **複数の実行モード**:
  - 通常モード: REST APIベースの定期実行
  - リアルタイムモード: WebSocketによるリアルタイムデータ取引
- **移動平均クロス戦略** - カスタマイズ可能なMA期間
- **リスク管理**:
  - 自動利確・損切り
  - ポジションサイズ管理
  - ペーパートレーディングモード
- **パフォーマンス追跡**:
  - 取引履歴の自動記録
  - 詳細なパフォーマンスレポート
  - リアルタイムロギング

## 📋 必要条件

- Python 3.8以上
- Bybit APIキー（取引権限付き）

## 🛠 セットアップ

1. **リポジトリのクローン**:
```bash
git clone https://github.com/koishichito/crypto-bot.git
cd crypto-bot
```

2. **Python仮想環境の作成**:
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

3. **依存関係のインストール**:
```bash
pip install -r requirements.txt
```

4. **環境変数の設定**:
```bash
cp .env.example .env
# .envファイルを編集してAPIキーを設定
```

## 🎮 使用方法

### 通常モード（推奨）
```bash
python main.py
```

### WebSocketリアルタイムモード
```bash
python bot_websocket.py
```

### パフォーマンスレポート表示
```bash
python show_performance.py
```

### ブレイクアウト戦略のバックテスト
```bash
python backtest_breakout.py
```

### ユニットテスト実行
```bash
python -m pytest tests/test_breakout_strategy.py
```

## ⚙️ 設定

`.env`ファイルで設定可能な項目:

| 変数名 | 説明 | デフォルト値 |
|--------|------|-------------|
| `API_KEY` | Bybit APIキー | - |
| `API_SECRET` | Bybit APIシークレット | - |
| `TRADING_PAIR` | 取引ペア | BTC/USDT |
| `TRADE_AMOUNT` | 1回の取引金額 (USDT) | 10 |
| `BOT_MODE` | `paper_trading` or `live_trading` | paper_trading |
| `STRATEGY` | 戦略選択 (`breakout` or `ma_cross`) | breakout |
| **ブレイクアウト戦略** | | |
| `ENTRY_LOOKBACK_PERIOD` | エントリー判定期間 | 20 |
| `EXIT_LOOKBACK_PERIOD` | エグジット判定期間 | 10 |
| `RISK_PER_TRADE` | 1トレードあたりリスク (%) | 1.0 |
| `USE_TURTLE_FILTER` | タートルフィルタ使用 | true |
| **MA戦略** | | |
| `FAST_MA_PERIOD` | 短期移動平均期間 | 10 |
| `SLOW_MA_PERIOD` | 長期移動平均期間 | 30 |
| `TAKE_PROFIT` | 利確ライン (%) | 2.0 |
| `STOP_LOSS` | 損切りライン (%) | 1.0 |
| `INTERVAL_SECONDS` | 実行間隔 (秒) | 60 |

## 📊 取引戦略

### 1. ブレイクアウト戦略（推奨）
暗号資産市場のトレンド性質に最適化された戦略です。

- **エントリー条件**:
  - 上昇ブレイク: 直近N期間（デフォルト20）の最高値を上回る → ロング
  - 下降ブレイク: 直近N期間の最安値を下回る → ショート（現物では見送り）
- **エグジット条件**:
  - 逆方向ブレイク: 直近M期間（デフォルト10）の最安値/最高値でトレイリングストップ
- **リスク管理**:
  - ポジションサイズ: 資産の1%リスク/トレード
  - タートルフィルタ: 直前の勝ちトレード後は次のシグナルを見送り
- **期待値**: バックテストで高い収益性を確認

### 2. 移動平均クロス戦略
従来の移動平均線を使用した戦略です。

- **エントリー条件**:
  - ゴールデンクロス: 短期MA > 長期MA → 買い
  - デッドクロス: 短期MA < 長期MA → 売り
- **エグジット条件**:
  - 利確: +2%（設定可能）
  - 損切り: -1%（設定可能）

## 📁 プロジェクト構成

```
crypto-bot/
├── main.py              # メイン取引ボット
├── bot_websocket.py     # WebSocket版ボット
├── utils.py             # ユーティリティ関数
├── show_performance.py  # パフォーマンス表示
├── requirements.txt     # Python依存関係
├── .env.example        # 環境変数テンプレート
└── logs/               # ログファイル
    ├── bot_*.log       # 実行ログ
    └── trades.json     # 取引履歴
```

## 🔒 セキュリティ

- APIキーは必ず`.env`ファイルに保存し、Gitにコミットしない
- 本番環境では最小限の権限のみ付与したAPIキーを使用
- ペーパートレーディングモードで十分にテストしてから実取引へ

## 📈 パフォーマンス指標

レポートに含まれる指標:
- 総取引数・損益
- 勝率・プロフィットファクター
- 最大利益・最大損失
- 売買方向別分析
- シンボル別分析

## 🤝 貢献

プルリクエストを歓迎します。大きな変更の場合は、まずイシューを作成して変更内容について議論してください。

## ⚠️ 免責事項

このボットは教育目的で作成されています。実際の取引に使用する場合は自己責任で行ってください。仮想通貨取引にはリスクが伴います。