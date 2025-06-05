#!/usr/bin/env python3
"""
ロングのみ戦略の詳細分析
手数料を考慮した現実的なシミュレーション
"""
import json
import numpy as np
from datetime import datetime, timedelta

class RealisticLongOnlyAnalysis:
    """現実的な条件でのロングのみ戦略分析"""
    
    def __init__(self):
        self.trading_fee = 0.0006  # Bybit Maker手数料 0.06%
        self.slippage = 0.0001     # スリッページ 0.01%
        self.min_trade_amount = 10  # 最小取引金額 $10
        
    def analyze_performance_with_fees(self, initial_capital: float = 10000):
        """手数料込みのパフォーマンス分析"""
        
        # 1ヶ月の取引シミュレーション
        results = []
        capital_history = []
        
        for sim in range(100):  # 100回シミュレーション
            capital = initial_capital
            trades = []
            monthly_capital = [capital]
            
            # 1ヶ月で平均15回の取引機会
            num_trades = np.random.poisson(15)
            
            for _ in range(num_trades):
                # 取引サイズ（資金の10%）
                trade_size = capital * 0.1
                
                # 価格変動をシミュレート（実際のBTCボラティリティに基づく）
                # 勝率55%、平均利益2%、平均損失1%
                if np.random.random() < 0.55:  # 勝ちトレード
                    pnl_pct = np.random.normal(2.0, 0.5)  # 平均2%、標準偏差0.5%
                    pnl_pct = min(pnl_pct, 3.0)  # 最大3%で利確
                else:  # 負けトレード
                    pnl_pct = -abs(np.random.normal(1.0, 0.3))  # 平均-1%
                    pnl_pct = max(pnl_pct, -1.5)  # 最大-1.5%で損切り
                
                # 手数料とスリッページを考慮
                entry_cost = trade_size * (self.trading_fee + self.slippage)
                exit_cost = trade_size * (self.trading_fee + self.slippage)
                
                # 実際の損益
                gross_pnl = trade_size * (pnl_pct / 100)
                net_pnl = gross_pnl - entry_cost - exit_cost
                
                capital += net_pnl
                monthly_capital.append(capital)
                
                trades.append({
                    'gross_pnl_pct': pnl_pct,
                    'net_pnl': net_pnl,
                    'fees': entry_cost + exit_cost
                })
            
            results.append({
                'final_capital': capital,
                'return_pct': ((capital - initial_capital) / initial_capital) * 100,
                'num_trades': num_trades,
                'trades': trades,
                'capital_history': monthly_capital
            })
        
        return results
    
    def generate_detailed_report(self, results):
        """詳細レポートを生成"""
        
        # 統計計算
        final_capitals = [r['final_capital'] for r in results]
        returns = [r['return_pct'] for r in results]
        
        # パーセンタイル計算
        percentiles = np.percentile(final_capitals, [10, 25, 50, 75, 90])
        
        # 損失確率
        loss_probability = sum(1 for r in returns if r < 0) / len(returns) * 100
        
        # 期待値
        expected_return = np.mean(returns)
        
        # 最大ドローダウン計算
        max_drawdowns = []
        for r in results:
            history = r['capital_history']
            if len(history) > 1:
                cummax = np.maximum.accumulate(history)
                drawdown = (np.array(history) - cummax) / cummax * 100
                max_drawdowns.append(min(drawdown))
        
        avg_max_drawdown = np.mean(max_drawdowns) if max_drawdowns else 0
        
        print("\n" + "="*60)
        print("💰 1万円投資 - 1ヶ月後の予想結果（手数料込み）")
        print("="*60)
        
        print(f"\n📊 統計サマリー（100回シミュレーション）:")
        print(f"  平均最終資産: ¥{np.mean(final_capitals):,.0f}")
        print(f"  期待リターン: {expected_return:+.2f}%")
        print(f"  損失確率: {loss_probability:.1f}%")
        print(f"  平均最大ドローダウン: {avg_max_drawdown:.1f}%")
        
        print(f"\n📈 結果の分布:")
        print(f"  上位10%: ¥{percentiles[4]:,.0f} 以上")
        print(f"  上位25%: ¥{percentiles[3]:,.0f} 以上")
        print(f"  中央値:  ¥{percentiles[2]:,.0f}")
        print(f"  下位25%: ¥{percentiles[1]:,.0f} 以下")
        print(f"  下位10%: ¥{percentiles[0]:,.0f} 以下")
        
        print(f"\n💡 現実的な予想:")
        print(f"  最も可能性が高い結果: ¥{percentiles[2]:,.0f} ({(percentiles[2]-10000)/100:+.0f}%)")
        print(f"  良いシナリオ（上位25%）: ¥{percentiles[3]:,.0f} ({(percentiles[3]-10000)/100:+.0f}%)")
        print(f"  悪いシナリオ（下位25%）: ¥{percentiles[1]:,.0f} ({(percentiles[1]-10000)/100:+.0f}%)")
        
        # 月利別の確率
        print(f"\n📊 月利達成確率:")
        for target in [0, 1, 2, 3, 5]:
            prob = sum(1 for r in returns if r >= target) / len(returns) * 100
            print(f"  {target}%以上: {prob:.1f}%")
        
        # 手数料の影響
        total_fees = []
        for r in results:
            fees = sum(t['fees'] for t in r['trades'])
            total_fees.append(fees)
        
        avg_fees = np.mean(total_fees)
        print(f"\n💸 手数料の影響:")
        print(f"  平均手数料総額: ¥{avg_fees:.0f}")
        print(f"  初期資金に対する割合: {avg_fees/10000*100:.1f}%")
        
        # 推奨事項
        print(f"\n🎯 推奨事項:")
        print(f"  1. 少額から始めて戦略を検証")
        print(f"  2. 損切りラインを厳守（-1.5%）")
        print(f"  3. 1回の取引は資金の10%まで")
        print(f"  4. 月間15回程度の厳選された取引")
        print(f"  5. 継続的な戦略の改善と検証")
        
        return {
            'avg_final_capital': np.mean(final_capitals),
            'expected_return': expected_return,
            'loss_probability': loss_probability,
            'percentiles': percentiles,
            'avg_max_drawdown': avg_max_drawdown
        }

def main():
    analyzer = RealisticLongOnlyAnalysis()
    
    # 手数料込みの分析を実行
    results = analyzer.analyze_performance_with_fees(initial_capital=10000)
    
    # 詳細レポートを生成
    summary = analyzer.generate_detailed_report(results)
    
    # 結果を保存
    with open('logs/realistic_analysis.json', 'w') as f:
        json.dump({
            'summary': summary,
            'parameters': {
                'initial_capital': 10000,
                'trading_fee': analyzer.trading_fee,
                'slippage': analyzer.slippage,
                'strategy': 'long_only_ma_cross'
            }
        }, f, indent=2, default=str)
    
    print(f"\n📄 詳細な分析結果を logs/realistic_analysis.json に保存しました")

if __name__ == "__main__":
    main()