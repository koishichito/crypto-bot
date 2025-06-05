#!/usr/bin/env python3
"""
ブレイクアウト戦略のバックテスト
過去データを使用して戦略のパフォーマンスを検証
"""
import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import pandas as pd
import numpy as np
from loguru import logger
import aiohttp

# ログ設定
logger.remove()
logger.add(lambda msg: print(msg), level="INFO", format="{time:HH:mm:ss} | {level} | {message}")

class BreakoutBacktest:
    """ブレイクアウト戦略のバックテスト"""
    
    def __init__(self, initial_capital: float = 10000):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions = []
        self.trades = []
        self.equity_curve = [initial_capital]
        
        # 戦略パラメータ
        self.entry_lookback = 20
        self.exit_lookback = 10
        self.risk_per_trade = 0.01
        self.use_turtle_filter = True
        self.last_trade_profitable = False
        
        # 手数料とスリッページ
        self.commission_rate = 0.0006  # 0.06%
        self.slippage = 0.0001  # 0.01%
    
    async def fetch_historical_data(self, symbol: str = 'BTCUSDT', interval: str = '1h', days: int = 365) -> pd.DataFrame:
        """Bybitから過去データを取得"""
        logger.info(f"Fetching {days} days of {interval} data for {symbol}")
        
        all_data = []
        end_time = int(datetime.now().timestamp() * 1000)
        start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
        
        # APIレート制限を考慮して分割取得
        async with aiohttp.ClientSession() as session:
            current_end = end_time
            
            while current_end > start_time:
                url = 'https://api.bybit.com/v5/market/kline'
                params = {
                    'category': 'spot',
                    'symbol': symbol,
                    'interval': '60',  # 1時間
                    'end': current_end,
                    'limit': 1000
                }
                
                try:
                    async with session.get(url, params=params) as response:
                        data = await response.json()
                        
                        if data['retCode'] == 0:
                            klines = data['result']['list']
                            if not klines:
                                break
                            
                            all_data.extend(klines)
                            # 最も古いデータのタイムスタンプを次回の終了時刻に
                            current_end = int(klines[-1][0]) - 1
                            
                            logger.debug(f"Fetched {len(klines)} candles, total: {len(all_data)}")
                            await asyncio.sleep(0.1)  # レート制限対策
                        else:
                            logger.error(f"API error: {data}")
                            break
                except Exception as e:
                    logger.error(f"Error fetching data: {e}")
                    break
        
        if not all_data:
            logger.error("No data fetched")
            return pd.DataFrame()
        
        # データフレームに変換
        df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
        df['timestamp'] = pd.to_datetime(df['timestamp'].astype(int), unit='ms')
        df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        logger.info(f"Loaded {len(df)} candles from {df['timestamp'].min()} to {df['timestamp'].max()}")
        return df
    
    def calculate_breakout_levels(self, df: pd.DataFrame, index: int, lookback: int) -> Tuple[float, float]:
        """指定インデックスでのブレイクアウトレベルを計算"""
        if index < lookback:
            return None, None
        
        high_range = df['high'].iloc[index-lookback:index]
        low_range = df['low'].iloc[index-lookback:index]
        
        return high_range.max(), low_range.min()
    
    def calculate_position_size(self, entry_price: float, stop_price: float) -> float:
        """リスクベースのポジションサイズを計算"""
        risk_per_unit = abs(entry_price - stop_price)
        risk_amount = self.capital * self.risk_per_trade
        
        if risk_per_unit > 0:
            return risk_amount / risk_per_unit
        else:
            return 0
    
    def execute_backtest(self, df: pd.DataFrame):
        """バックテストを実行"""
        position = None
        
        for i in range(self.entry_lookback, len(df)):
            current_price = df['close'].iloc[i]
            current_time = df['timestamp'].iloc[i]
            
            if position is None:
                # エントリーシグナルをチェック
                entry_high, entry_low = self.calculate_breakout_levels(df, i, self.entry_lookback)
                
                if entry_high is None or entry_low is None:
                    continue
                
                # タートルフィルタ
                if self.use_turtle_filter and self.last_trade_profitable:
                    self.last_trade_profitable = False
                    continue
                
                # ブレイクアウト判定
                if current_price > entry_high:
                    # ロングエントリー
                    exit_high, exit_low = self.calculate_breakout_levels(df, i, self.exit_lookback)
                    if exit_low is None:
                        continue
                    
                    size = self.calculate_position_size(current_price, exit_low)
                    if size <= 0:
                        continue
                    
                    # 手数料とスリッページ考慮
                    entry_cost = current_price * (1 + self.slippage + self.commission_rate)
                    cost = size * entry_cost
                    
                    if cost > self.capital:
                        size = self.capital / entry_cost * 0.95  # 資金の95%まで
                    
                    position = {
                        'type': 'long',
                        'entry_price': current_price,
                        'entry_cost': entry_cost,
                        'size': size,
                        'entry_time': current_time,
                        'stop_price': exit_low
                    }
                    
                    logger.debug(f"Long entry at {current_price:.2f}, size: {size:.6f}")
                
                elif current_price < entry_low:
                    # ショートエントリー（現物のみなのでスキップ）
                    pass
            
            else:
                # エグジットシグナルをチェック
                exit_high, exit_low = self.calculate_breakout_levels(df, i, self.exit_lookback)
                
                if position['type'] == 'long' and exit_low is not None:
                    if current_price <= exit_low:
                        # ロングエグジット
                        exit_price = current_price * (1 - self.slippage - self.commission_rate)
                        pnl = (exit_price - position['entry_cost']) * position['size']
                        pnl_pct = ((exit_price - position['entry_cost']) / position['entry_cost']) * 100
                        
                        self.capital += pnl
                        
                        trade = {
                            'entry_time': position['entry_time'],
                            'exit_time': current_time,
                            'type': position['type'],
                            'entry_price': position['entry_price'],
                            'exit_price': current_price,
                            'size': position['size'],
                            'pnl': pnl,
                            'pnl_pct': pnl_pct,
                            'capital_after': self.capital
                        }
                        self.trades.append(trade)
                        
                        # タートルフィルタ用の結果記録
                        self.last_trade_profitable = pnl > 0
                        
                        logger.debug(f"Long exit at {current_price:.2f}, PnL: {pnl:.2f} ({pnl_pct:.2f}%)")
                        position = None
            
            # 資産曲線を記録
            if position:
                # 含み益を考慮
                mark_to_market = position['size'] * (current_price - position['entry_cost'])
                self.equity_curve.append(self.capital + mark_to_market)
            else:
                self.equity_curve.append(self.capital)
    
    def calculate_metrics(self) -> Dict:
        """パフォーマンス指標を計算"""
        if not self.trades:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'total_return': 0,
                'sharpe_ratio': 0,
                'max_drawdown': 0
            }
        
        # 基本統計
        wins = [t for t in self.trades if t['pnl'] > 0]
        losses = [t for t in self.trades if t['pnl'] < 0]
        
        win_rate = len(wins) / len(self.trades) * 100
        avg_win = sum(t['pnl'] for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t['pnl'] for t in losses) / len(losses) if losses else 0
        
        # プロフィットファクター
        gross_profit = sum(t['pnl'] for t in wins)
        gross_loss = abs(sum(t['pnl'] for t in losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # リターン
        total_return = ((self.capital - self.initial_capital) / self.initial_capital) * 100
        
        # シャープレシオ（簡易版）
        if len(self.equity_curve) > 1:
            returns = pd.Series(self.equity_curve).pct_change().dropna()
            sharpe_ratio = returns.mean() / returns.std() * np.sqrt(252 * 24) if returns.std() > 0 else 0
        else:
            sharpe_ratio = 0
        
        # 最大ドローダウン
        equity_series = pd.Series(self.equity_curve)
        rolling_max = equity_series.expanding().max()
        drawdown = (equity_series - rolling_max) / rolling_max
        max_drawdown = drawdown.min() * 100
        
        return {
            'total_trades': len(self.trades),
            'winning_trades': len(wins),
            'losing_trades': len(losses),
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'total_return': total_return,
            'final_capital': self.capital,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown
        }
    
    def print_report(self):
        """バックテスト結果を表示"""
        metrics = self.calculate_metrics()
        
        print("\n" + "="*60)
        print("📊 ブレイクアウト戦略バックテスト結果")
        print("="*60)
        
        print(f"\n💰 資産推移:")
        print(f"  初期資産: ${self.initial_capital:,.2f}")
        print(f"  最終資産: ${metrics['final_capital']:,.2f}")
        print(f"  総リターン: {metrics['total_return']:.2f}%")
        
        print(f"\n📈 取引統計:")
        print(f"  総取引数: {metrics['total_trades']}")
        print(f"  勝ちトレード: {metrics['winning_trades']}")
        print(f"  負けトレード: {metrics['losing_trades']}")
        print(f"  勝率: {metrics['win_rate']:.1f}%")
        
        print(f"\n💵 損益統計:")
        print(f"  平均利益: ${metrics['avg_win']:.2f}")
        print(f"  平均損失: ${metrics['avg_loss']:.2f}")
        print(f"  プロフィットファクター: {metrics['profit_factor']:.2f}")
        
        print(f"\n📊 リスク指標:")
        print(f"  シャープレシオ: {metrics['sharpe_ratio']:.2f}")
        print(f"  最大ドローダウン: {metrics['max_drawdown']:.1f}%")
        
        # パラメータ情報
        print(f"\n⚙️ 戦略パラメータ:")
        print(f"  エントリー期間: {self.entry_lookback}")
        print(f"  エグジット期間: {self.exit_lookback}")
        print(f"  リスク/トレード: {self.risk_per_trade*100:.1f}%")
        print(f"  タートルフィルタ: {'有効' if self.use_turtle_filter else '無効'}")
        
        print("\n" + "="*60)

async def run_parameter_optimization():
    """パラメータ最適化"""
    print("\n🔧 パラメータ最適化を実行中...")
    
    # パラメータ候補
    entry_periods = [10, 20, 30, 50]
    exit_periods = [5, 10, 15, 20]
    risk_levels = [0.005, 0.01, 0.015, 0.02]
    
    best_result = None
    best_params = None
    best_metric = -float('inf')
    
    # データを一度だけ取得
    backtest = BreakoutBacktest()
    df = await backtest.fetch_historical_data(days=365)
    
    if df.empty:
        print("データ取得に失敗しました")
        return
    
    results = []
    
    for entry in entry_periods:
        for exit in exit_periods:
            if exit >= entry:  # エグジット期間はエントリー期間より短い
                continue
            
            for risk in risk_levels:
                # バックテスト実行
                bt = BreakoutBacktest(initial_capital=10000)
                bt.entry_lookback = entry
                bt.exit_lookback = exit
                bt.risk_per_trade = risk
                
                bt.execute_backtest(df)
                metrics = bt.calculate_metrics()
                
                # 評価指標（シャープレシオ * プロフィットファクター）
                if metrics['total_trades'] > 10:  # 最低取引数
                    score = metrics['sharpe_ratio'] * min(metrics['profit_factor'], 3.0)
                    
                    results.append({
                        'entry': entry,
                        'exit': exit,
                        'risk': risk,
                        'score': score,
                        'return': metrics['total_return'],
                        'trades': metrics['total_trades'],
                        'win_rate': metrics['win_rate'],
                        'sharpe': metrics['sharpe_ratio'],
                        'pf': metrics['profit_factor']
                    })
                    
                    if score > best_metric:
                        best_metric = score
                        best_params = (entry, exit, risk)
                        best_result = metrics
    
    # 結果を表示
    print("\n📊 最適化結果（上位5つ）:")
    sorted_results = sorted(results, key=lambda x: x['score'], reverse=True)[:5]
    
    for i, r in enumerate(sorted_results, 1):
        print(f"\n{i}. Entry={r['entry']}, Exit={r['exit']}, Risk={r['risk']*100:.1f}%")
        print(f"   スコア: {r['score']:.2f}, リターン: {r['return']:.1f}%, 勝率: {r['win_rate']:.1f}%")
        print(f"   シャープ: {r['sharpe']:.2f}, PF: {r['pf']:.2f}, 取引数: {r['trades']}")
    
    if best_params:
        print(f"\n✨ 最適パラメータ: Entry={best_params[0]}, Exit={best_params[1]}, Risk={best_params[2]*100:.1f}%")

async def main():
    """メイン関数"""
    print("\n🚀 ブレイクアウト戦略バックテスト開始")
    
    # 1. 基本バックテスト（デフォルトパラメータ）
    backtest = BreakoutBacktest(initial_capital=10000)
    
    # 過去データを取得
    df = await backtest.fetch_historical_data(symbol='BTCUSDT', days=365)
    
    if df.empty:
        print("データ取得に失敗しました")
        return
    
    # バックテスト実行
    backtest.execute_backtest(df)
    
    # 結果表示
    backtest.print_report()
    
    # 取引履歴を保存
    if backtest.trades:
        os.makedirs('logs', exist_ok=True)
        with open('logs/breakout_backtest.json', 'w') as f:
            json.dump({
                'trades': backtest.trades,
                'metrics': backtest.calculate_metrics(),
                'parameters': {
                    'entry_lookback': backtest.entry_lookback,
                    'exit_lookback': backtest.exit_lookback,
                    'risk_per_trade': backtest.risk_per_trade
                }
            }, f, indent=2, default=str)
        print("\n💾 詳細結果を logs/breakout_backtest.json に保存しました")
    
    # 2. パラメータ最適化（オプション）
    optimize = input("\nパラメータ最適化を実行しますか？ (y/n): ")
    if optimize.lower() == 'y':
        await run_parameter_optimization()

if __name__ == "__main__":
    asyncio.run(main())