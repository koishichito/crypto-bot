"""
ユーティリティ関数
"""
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import pandas as pd
import numpy as np
from loguru import logger

class TradingMetrics:
    """取引パフォーマンスの計算"""
    
    @staticmethod
    def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.0) -> float:
        """シャープレシオを計算"""
        if len(returns) < 2:
            return 0.0
        
        excess_returns = returns - risk_free_rate
        return np.sqrt(252) * (excess_returns.mean() / excess_returns.std()) if excess_returns.std() > 0 else 0.0
    
    @staticmethod
    def calculate_max_drawdown(equity_curve: pd.Series) -> Tuple[float, datetime, datetime]:
        """最大ドローダウンを計算"""
        cummax = equity_curve.cummax()
        drawdown = (equity_curve - cummax) / cummax
        
        max_dd = drawdown.min()
        max_dd_idx = drawdown.idxmin()
        
        # ドローダウン開始点を見つける
        peak_idx = equity_curve[:max_dd_idx].idxmax()
        
        return max_dd * 100, peak_idx, max_dd_idx
    
    @staticmethod
    def calculate_win_rate(trades: List[Dict]) -> float:
        """勝率を計算"""
        if not trades:
            return 0.0
        
        wins = sum(1 for trade in trades if trade.get('pnl_usdt', 0) > 0)
        return (wins / len(trades)) * 100
    
    @staticmethod
    def calculate_profit_factor(trades: List[Dict]) -> float:
        """プロフィットファクターを計算"""
        if not trades:
            return 0.0
        
        gross_profit = sum(trade['pnl_usdt'] for trade in trades if trade.get('pnl_usdt', 0) > 0)
        gross_loss = abs(sum(trade['pnl_usdt'] for trade in trades if trade.get('pnl_usdt', 0) < 0))
        
        return gross_profit / gross_loss if gross_loss > 0 else float('inf')

class PerformanceReporter:
    """パフォーマンスレポート生成"""
    
    def __init__(self, trades_file: str = 'logs/trades.json'):
        self.trades_file = trades_file
        self.metrics = TradingMetrics()
    
    def load_trades(self) -> List[Dict]:
        """取引履歴を読み込み"""
        if not os.path.exists(self.trades_file):
            return []
        
        try:
            with open(self.trades_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading trades: {e}")
            return []
    
    def generate_report(self) -> Dict:
        """パフォーマンスレポートを生成"""
        trades = self.load_trades()
        
        if not trades:
            return {
                'status': 'No trades found',
                'total_trades': 0
            }
        
        # 基本統計
        total_trades = len(trades)
        total_pnl = sum(trade['pnl_usdt'] for trade in trades)
        avg_pnl = total_pnl / total_trades
        
        # 勝率とプロフィットファクター
        win_rate = self.metrics.calculate_win_rate(trades)
        profit_factor = self.metrics.calculate_profit_factor(trades)
        
        # 最大利益・損失
        pnls = [trade['pnl_usdt'] for trade in trades]
        max_profit = max(pnls) if pnls else 0
        max_loss = min(pnls) if pnls else 0
        
        # 期間
        if trades:
            first_trade = datetime.fromisoformat(trades[0]['timestamp'])
            last_trade = datetime.fromisoformat(trades[-1]['timestamp'])
            trading_days = (last_trade - first_trade).days + 1
        else:
            trading_days = 0
        
        report = {
            'period': {
                'start': trades[0]['timestamp'] if trades else None,
                'end': trades[-1]['timestamp'] if trades else None,
                'days': trading_days
            },
            'summary': {
                'total_trades': total_trades,
                'total_pnl_usdt': round(total_pnl, 2),
                'avg_pnl_usdt': round(avg_pnl, 2),
                'win_rate_pct': round(win_rate, 2),
                'profit_factor': round(profit_factor, 2),
                'max_profit_usdt': round(max_profit, 2),
                'max_loss_usdt': round(max_loss, 2)
            },
            'by_side': self._analyze_by_side(trades),
            'by_symbol': self._analyze_by_symbol(trades),
            'recent_trades': trades[-10:]  # 最新10件
        }
        
        return report
    
    def _analyze_by_side(self, trades: List[Dict]) -> Dict:
        """売買方向別の分析"""
        buy_trades = [t for t in trades if t['side'] == 'Buy']
        sell_trades = [t for t in trades if t['side'] == 'Sell']
        
        return {
            'buy': {
                'count': len(buy_trades),
                'total_pnl': round(sum(t['pnl_usdt'] for t in buy_trades), 2) if buy_trades else 0,
                'win_rate': round(self.metrics.calculate_win_rate(buy_trades), 2)
            },
            'sell': {
                'count': len(sell_trades),
                'total_pnl': round(sum(t['pnl_usdt'] for t in sell_trades), 2) if sell_trades else 0,
                'win_rate': round(self.metrics.calculate_win_rate(sell_trades), 2)
            }
        }
    
    def _analyze_by_symbol(self, trades: List[Dict]) -> Dict:
        """シンボル別の分析"""
        symbols = set(t['symbol'] for t in trades)
        analysis = {}
        
        for symbol in symbols:
            symbol_trades = [t for t in trades if t['symbol'] == symbol]
            analysis[symbol] = {
                'count': len(symbol_trades),
                'total_pnl': round(sum(t['pnl_usdt'] for t in symbol_trades), 2),
                'win_rate': round(self.metrics.calculate_win_rate(symbol_trades), 2)
            }
        
        return analysis
    
    def print_report(self):
        """レポートを表示"""
        report = self.generate_report()
        
        if report.get('status') == 'No trades found':
            print("\n📊 No trades found yet.")
            return
        
        print("\n" + "="*60)
        print("📊 TRADING PERFORMANCE REPORT")
        print("="*60)
        
        # 期間
        period = report['period']
        print(f"\n📅 Period: {period['start']} to {period['end']} ({period['days']} days)")
        
        # サマリー
        summary = report['summary']
        print(f"\n📈 Summary:")
        print(f"  Total Trades: {summary['total_trades']}")
        print(f"  Total P&L: ${summary['total_pnl_usdt']:,.2f}")
        print(f"  Average P&L: ${summary['avg_pnl_usdt']:,.2f}")
        print(f"  Win Rate: {summary['win_rate_pct']:.1f}%")
        print(f"  Profit Factor: {summary['profit_factor']:.2f}")
        print(f"  Max Profit: ${summary['max_profit_usdt']:,.2f}")
        print(f"  Max Loss: ${summary['max_loss_usdt']:,.2f}")
        
        # 売買方向別
        by_side = report['by_side']
        print(f"\n🔄 By Side:")
        print(f"  Buy: {by_side['buy']['count']} trades, ${by_side['buy']['total_pnl']:,.2f} P&L, {by_side['buy']['win_rate']:.1f}% win rate")
        print(f"  Sell: {by_side['sell']['count']} trades, ${by_side['sell']['total_pnl']:,.2f} P&L, {by_side['sell']['win_rate']:.1f}% win rate")
        
        # 最近の取引
        print(f"\n📝 Recent Trades:")
        for trade in report['recent_trades'][-5:]:
            timestamp = datetime.fromisoformat(trade['timestamp']).strftime('%Y-%m-%d %H:%M')
            print(f"  {timestamp}: {trade['side']} {trade['symbol']} - P&L: ${trade['pnl_usdt']:+,.2f} ({trade['pnl_pct']:+.2f}%)")
        
        print("\n" + "="*60)

def print_banner():
    """バナーを表示"""
    banner = """
╔═══════════════════════════════════════════════════════════╗
║             🤖 CRYPTO TRADING BOT (pybotters)             ║
║                      Bybit Exchange                       ║
╚═══════════════════════════════════════════════════════════╝
    """
    print(banner)

if __name__ == "__main__":
    # テスト用
    reporter = PerformanceReporter()
    reporter.print_report()