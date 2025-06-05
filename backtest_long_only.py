#!/usr/bin/env python3
"""
ロングのみの取引戦略バックテスト
1万円を投入した場合の1ヶ月後の総額をシミュレーション
"""
import json
import random
from datetime import datetime, timedelta
import numpy as np
from typing import List, Dict
import os

class LongOnlyBacktest:
    """ロングのみの取引戦略のバックテスト"""
    
    def __init__(self, initial_capital: float = 10000, leverage: float = 1.0):
        self.initial_capital = initial_capital  # 初期資金（円）
        self.capital = initial_capital
        self.leverage = leverage
        self.trades = []
        self.daily_balance = []
        
    def simulate_price_movement(self, days: int = 30) -> List[Dict]:
        """BTCの価格変動をシミュレート（実際の市場に近い動き）"""
        # 現在のBTC価格（約1,570万円）
        base_price_jpy = 15700000
        prices = []
        
        # トレンドとボラティリティの設定
        trend = 0.0002  # 日次0.02%の上昇トレンド（月間約0.6%）
        volatility = 0.015  # 日次1.5%のボラティリティ
        
        current_price = base_price_jpy
        
        for day in range(days * 24):  # 1時間ごとのデータ
            # ランダムウォーク + トレンド
            change = np.random.normal(trend/24, volatility/np.sqrt(24))
            current_price = current_price * (1 + change)
            
            prices.append({
                'timestamp': datetime.now() - timedelta(hours=(days*24-day)),
                'price': current_price,
                'hour': day
            })
        
        return prices
    
    def detect_ma_cross_signals(self, prices: List[Dict]) -> List[Dict]:
        """移動平均クロスのシグナルを検出"""
        signals = []
        price_values = [p['price'] for p in prices]
        
        # 移動平均の計算（10時間と30時間）
        fast_period = 10
        slow_period = 30
        
        for i in range(slow_period, len(prices)):
            fast_ma = np.mean(price_values[i-fast_period:i])
            slow_ma = np.mean(price_values[i-slow_period:i])
            
            fast_ma_prev = np.mean(price_values[i-fast_period-1:i-1])
            slow_ma_prev = np.mean(price_values[i-slow_period-1:i-1])
            
            # ゴールデンクロス（買いシグナル）
            if fast_ma_prev <= slow_ma_prev and fast_ma > slow_ma:
                signals.append({
                    'type': 'buy',
                    'price': prices[i]['price'],
                    'timestamp': prices[i]['timestamp'],
                    'index': i
                })
        
        return signals
    
    def execute_long_only_strategy(self, prices: List[Dict], signals: List[Dict]):
        """ロングのみの戦略を実行"""
        position = None
        trade_amount = self.initial_capital * 0.1  # 1回の取引は資金の10%
        
        for signal in signals:
            current_price = signal['price']
            signal_index = signal['index']
            
            if position is None:
                # エントリー
                btc_amount = (trade_amount / current_price) * self.leverage
                position = {
                    'entry_price': current_price,
                    'amount': btc_amount,
                    'entry_time': signal['timestamp'],
                    'entry_capital': self.capital
                }
                
            else:
                # 利確・損切りチェック（シグナル後の価格推移を確認）
                for i in range(signal_index, min(signal_index + 240, len(prices))):  # 最大10日間保有
                    check_price = prices[i]['price']
                    pnl_pct = ((check_price - position['entry_price']) / position['entry_price']) * 100
                    
                    # 利確条件（2%）または損切り条件（-1%）
                    if pnl_pct >= 2.0 or pnl_pct <= -1.0:
                        # ポジションクローズ
                        pnl_jpy = (check_price - position['entry_price']) * position['amount']
                        self.capital += pnl_jpy
                        
                        self.trades.append({
                            'entry_price': position['entry_price'],
                            'exit_price': check_price,
                            'pnl_pct': pnl_pct,
                            'pnl_jpy': pnl_jpy,
                            'duration_hours': (prices[i]['timestamp'] - position['entry_time']).total_seconds() / 3600,
                            'exit_reason': 'Take Profit' if pnl_pct >= 2.0 else 'Stop Loss',
                            'capital_after': self.capital
                        })
                        
                        position = None
                        break
                
                # タイムアウト（10日経過）した場合もクローズ
                if position is not None and i == min(signal_index + 240, len(prices)) - 1:
                    exit_price = prices[i]['price']
                    pnl_pct = ((exit_price - position['entry_price']) / position['entry_price']) * 100
                    pnl_jpy = (exit_price - position['entry_price']) * position['amount']
                    self.capital += pnl_jpy
                    
                    self.trades.append({
                        'entry_price': position['entry_price'],
                        'exit_price': exit_price,
                        'pnl_pct': pnl_pct,
                        'pnl_jpy': pnl_jpy,
                        'duration_hours': 240,
                        'exit_reason': 'Timeout',
                        'capital_after': self.capital
                    })
                    
                    position = None
        
        # 最終的にポジションが残っている場合はクローズ
        if position is not None:
            final_price = prices[-1]['price']
            pnl_pct = ((final_price - position['entry_price']) / position['entry_price']) * 100
            pnl_jpy = (final_price - position['entry_price']) * position['amount']
            self.capital += pnl_jpy
            
            self.trades.append({
                'entry_price': position['entry_price'],
                'exit_price': final_price,
                'pnl_pct': pnl_pct,
                'pnl_jpy': pnl_jpy,
                'duration_hours': (prices[-1]['timestamp'] - position['entry_time']).total_seconds() / 3600,
                'exit_reason': 'End of Period',
                'capital_after': self.capital
            })
    
    def generate_report(self) -> Dict:
        """パフォーマンスレポートを生成"""
        if not self.trades:
            return {'error': 'No trades executed'}
        
        # 基本統計
        total_trades = len(self.trades)
        winning_trades = [t for t in self.trades if t['pnl_jpy'] > 0]
        losing_trades = [t for t in self.trades if t['pnl_jpy'] < 0]
        
        win_rate = (len(winning_trades) / total_trades) * 100 if total_trades > 0 else 0
        
        # 損益計算
        total_pnl = sum(t['pnl_jpy'] for t in self.trades)
        avg_pnl = total_pnl / total_trades if total_trades > 0 else 0
        
        # 最大利益・損失
        max_profit = max(t['pnl_jpy'] for t in self.trades) if self.trades else 0
        max_loss = min(t['pnl_jpy'] for t in self.trades) if self.trades else 0
        
        # リターン計算
        total_return_pct = ((self.capital - self.initial_capital) / self.initial_capital) * 100
        
        return {
            'initial_capital': self.initial_capital,
            'final_capital': self.capital,
            'total_return_jpy': self.capital - self.initial_capital,
            'total_return_pct': total_return_pct,
            'total_trades': total_trades,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_pnl': avg_pnl,
            'max_profit': max_profit,
            'max_loss': max_loss,
            'avg_win': sum(t['pnl_jpy'] for t in winning_trades) / len(winning_trades) if winning_trades else 0,
            'avg_loss': sum(t['pnl_jpy'] for t in losing_trades) / len(losing_trades) if losing_trades else 0,
            'trades': self.trades
        }

def main():
    print("\n" + "="*60)
    print("📊 ロングのみ戦略 - 1ヶ月バックテスト")
    print("="*60)
    
    # バックテストを複数回実行して平均を取る
    results = []
    num_simulations = 10
    
    print(f"\n🎲 {num_simulations}回のシミュレーションを実行中...")
    
    for i in range(num_simulations):
        backtest = LongOnlyBacktest(initial_capital=10000)
        
        # 価格データを生成
        prices = backtest.simulate_price_movement(days=30)
        
        # シグナルを検出
        signals = backtest.detect_ma_cross_signals(prices)
        
        # 戦略を実行
        backtest.execute_long_only_strategy(prices, signals)
        
        # 結果を保存
        report = backtest.generate_report()
        results.append(report)
        
        print(f"  シミュレーション {i+1}: 最終資産 ¥{report['final_capital']:,.0f} ({report['total_return_pct']:+.1f}%)")
    
    # 平均結果を計算
    avg_final_capital = np.mean([r['final_capital'] for r in results])
    avg_return_pct = np.mean([r['total_return_pct'] for r in results])
    avg_trades = np.mean([r['total_trades'] for r in results])
    avg_win_rate = np.mean([r['win_rate'] for r in results])
    
    best_result = max(results, key=lambda x: x['final_capital'])
    worst_result = min(results, key=lambda x: x['final_capital'])
    
    # 結果を表示
    print("\n" + "="*60)
    print("📈 シミュレーション結果サマリー")
    print("="*60)
    
    print(f"\n💰 初期投資額: ¥10,000")
    print(f"\n📊 1ヶ月後の結果（{num_simulations}回の平均）:")
    print(f"  平均最終資産: ¥{avg_final_capital:,.0f}")
    print(f"  平均リターン: {avg_return_pct:+.1f}%")
    print(f"  平均取引回数: {avg_trades:.1f}回")
    print(f"  平均勝率: {avg_win_rate:.1f}%")
    
    print(f"\n🎯 最良ケース:")
    print(f"  最終資産: ¥{best_result['final_capital']:,.0f} ({best_result['total_return_pct']:+.1f}%)")
    print(f"  取引回数: {best_result['total_trades']}回")
    print(f"  勝率: {best_result['win_rate']:.1f}%")
    
    print(f"\n⚠️ 最悪ケース:")
    print(f"  最終資産: ¥{worst_result['final_capital']:,.0f} ({worst_result['total_return_pct']:+.1f}%)")
    print(f"  取引回数: {worst_result['total_trades']}回")
    print(f"  勝率: {worst_result['win_rate']:.1f}%")
    
    # 代表的な取引例を表示
    print(f"\n📝 代表的な取引例（最良ケースより）:")
    for i, trade in enumerate(best_result['trades'][:5], 1):
        print(f"  取引{i}: {trade['exit_reason']} - "
              f"損益: ¥{trade['pnl_jpy']:+,.0f} ({trade['pnl_pct']:+.1f}%), "
              f"保有時間: {trade['duration_hours']:.1f}時間")
    
    # リスク警告
    print(f"\n⚠️ リスク警告:")
    print(f"  - これはシミュレーション結果です")
    print(f"  - 実際の市場では手数料、スリッページが発生します")
    print(f"  - 過去のパフォーマンスは将来を保証しません")
    
    # 詳細レポートを保存
    os.makedirs('logs', exist_ok=True)
    with open('logs/backtest_long_only.json', 'w') as f:
        json.dump({
            'summary': {
                'avg_final_capital': avg_final_capital,
                'avg_return_pct': avg_return_pct,
                'avg_trades': avg_trades,
                'avg_win_rate': avg_win_rate
            },
            'all_results': results
        }, f, indent=2, default=str)
    
    print(f"\n💾 詳細レポートを logs/backtest_long_only.json に保存しました")

if __name__ == "__main__":
    main()