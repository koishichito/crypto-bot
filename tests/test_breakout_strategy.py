#!/usr/bin/env python3
"""
ブレイクアウト戦略のユニットテスト
"""
import unittest
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
import sys
from pathlib import Path

# プロジェクトのルートをPythonパスに追加
sys.path.append(str(Path(__file__).parent.parent))

from bot.strategies.breakout import BreakoutStrategy

class TestBreakoutStrategy(unittest.TestCase):
    """ブレイクアウト戦略のテストケース"""
    
    def setUp(self):
        """テストセットアップ"""
        self.strategy = BreakoutStrategy(
            symbol='BTCUSDT',
            trade_amount=100,
            entry_lookback=20,
            exit_lookback=10,
            risk_per_trade=0.01
        )
    
    def test_initialization(self):
        """初期化のテスト"""
        self.assertEqual(self.strategy.symbol, 'BTCUSDT')
        self.assertEqual(self.strategy.trade_amount, 100)
        self.assertEqual(self.strategy.entry_lookback, 20)
        self.assertEqual(self.strategy.exit_lookback, 10)
        self.assertEqual(self.strategy.risk_per_trade, 0.01)
        self.assertTrue(self.strategy.use_turtle_filter)
        self.assertFalse(self.strategy.last_trade_profitable)
    
    def test_calculate_breakout_levels(self):
        """ブレイクアウトレベル計算のテスト"""
        # テストデータ作成
        data = {
            'timestamp': pd.date_range(start='2024-01-01', periods=30, freq='H'),
            'open': np.random.uniform(100, 110, 30),
            'high': np.random.uniform(105, 115, 30),
            'low': np.random.uniform(95, 105, 30),
            'close': np.random.uniform(100, 110, 30),
            'volume': np.random.uniform(1000, 2000, 30)
        }
        df = pd.DataFrame(data)
        
        # 最高値・最安値を設定
        df.loc[10:20, 'high'] = [120, 115, 118, 122, 119, 121, 117, 116, 120, 123, 119]
        df.loc[10:20, 'low'] = [90, 92, 88, 91, 89, 87, 93, 94, 86, 90, 91]
        
        # ブレイクアウトレベル計算
        highest, lowest = self.strategy.calculate_breakout_levels(df, 10)
        
        # 検証
        expected_highest = df['high'].iloc[-11:-1].max()
        expected_lowest = df['low'].iloc[-11:-1].min()
        self.assertEqual(highest, expected_highest)
        self.assertEqual(lowest, expected_lowest)
    
    def test_calculate_breakout_levels_insufficient_data(self):
        """データ不足時のブレイクアウトレベル計算"""
        df = pd.DataFrame({
            'timestamp': pd.date_range(start='2024-01-01', periods=5, freq='H'),
            'high': [105, 106, 107, 108, 109],
            'low': [95, 96, 97, 98, 99],
            'close': [100, 101, 102, 103, 104]
        })
        
        # 期間10でデータが5つしかない場合
        highest, lowest = self.strategy.calculate_breakout_levels(df, 10)
        self.assertIsNone(highest)
        self.assertIsNone(lowest)
    
    def test_bullish_breakout_signal(self):
        """上昇ブレイクアウトシグナルのテスト"""
        # モックデータ作成
        df = pd.DataFrame({
            'timestamp': pd.date_range(start='2024-01-01', periods=25, freq='H'),
            'high': [100 + i*0.1 for i in range(25)],
            'low': [95 + i*0.1 for i in range(25)],
            'close': [98 + i*0.1 for i in range(25)]
        })
        
        # 最後の価格を高値ブレイクアウトに設定
        df.loc[24, 'close'] = 110  # 直近20本の最高値を超える
        
        # モッククライアント
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value={
            'retCode': 0,
            'result': {
                'list': [[str(int(ts.timestamp() * 1000)), '100', str(h), str(l), str(c), '1000', '100000'] 
                        for ts, h, l, c in zip(df['timestamp'], df['high'], df['low'], df['close'])]
            }
        })
        mock_client.get = AsyncMock(return_value=mock_response)
        
        # シグナル計算
        loop = asyncio.get_event_loop()
        signal = loop.run_until_complete(self.strategy.calculate_signal(mock_client))
        
        self.assertEqual(signal, 'buy')
    
    def test_bearish_breakout_signal(self):
        """下降ブレイクアウトシグナルのテスト"""
        # モックデータ作成
        df = pd.DataFrame({
            'timestamp': pd.date_range(start='2024-01-01', periods=25, freq='H'),
            'high': [105 - i*0.1 for i in range(25)],
            'low': [100 - i*0.1 for i in range(25)],
            'close': [102 - i*0.1 for i in range(25)]
        })
        
        # 最後の価格を安値ブレイクアウトに設定
        df.loc[24, 'close'] = 90  # 直近20本の最安値を下回る
        
        # モッククライアント
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value={
            'retCode': 0,
            'result': {
                'list': [[str(int(ts.timestamp() * 1000)), '100', str(h), str(l), str(c), '1000', '100000'] 
                        for ts, h, l, c in zip(df['timestamp'], df['high'], df['low'], df['close'])]
            }
        })
        mock_client.get = AsyncMock(return_value=mock_response)
        
        # シグナル計算
        loop = asyncio.get_event_loop()
        signal = loop.run_until_complete(self.strategy.calculate_signal(mock_client))
        
        self.assertEqual(signal, 'sell')
    
    def test_no_breakout_signal(self):
        """ブレイクアウトなしのテスト"""
        # レンジ内で推移するデータ
        df = pd.DataFrame({
            'timestamp': pd.date_range(start='2024-01-01', periods=25, freq='H'),
            'high': [101 + np.sin(i/5) for i in range(25)],
            'low': [99 - np.sin(i/5) for i in range(25)],
            'close': [100 + np.sin(i/5)*0.5 for i in range(25)]
        })
        
        # モッククライアント
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value={
            'retCode': 0,
            'result': {
                'list': [[str(int(ts.timestamp() * 1000)), '100', str(h), str(l), str(c), '1000', '100000'] 
                        for ts, h, l, c in zip(df['timestamp'], df['high'], df['low'], df['close'])]
            }
        })
        mock_client.get = AsyncMock(return_value=mock_response)
        
        # シグナル計算
        loop = asyncio.get_event_loop()
        signal = loop.run_until_complete(self.strategy.calculate_signal(mock_client))
        
        self.assertEqual(signal, 'hold')
    
    def test_turtle_filter(self):
        """タートルフィルタのテスト"""
        # 直前のトレードが利益だった場合
        self.strategy.last_trade_profitable = True
        
        # ブレイクアウトが発生するデータ
        df = pd.DataFrame({
            'timestamp': pd.date_range(start='2024-01-01', periods=25, freq='H'),
            'high': [100 + i*0.1 for i in range(25)],
            'low': [95 + i*0.1 for i in range(25)],
            'close': [98 + i*0.1 for i in range(25)]
        })
        df.loc[24, 'close'] = 110  # ブレイクアウト
        
        # モッククライアント
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value={
            'retCode': 0,
            'result': {
                'list': [[str(int(ts.timestamp() * 1000)), '100', str(h), str(l), str(c), '1000', '100000'] 
                        for ts, h, l, c in zip(df['timestamp'], df['high'], df['low'], df['close'])]
            }
        })
        mock_client.get = AsyncMock(return_value=mock_response)
        
        # シグナル計算（フィルタによりholdになるはず）
        loop = asyncio.get_event_loop()
        signal = loop.run_until_complete(self.strategy.calculate_signal(mock_client))
        
        self.assertEqual(signal, 'hold')
        self.assertFalse(self.strategy.last_trade_profitable)  # フィルタがリセットされる
    
    def test_position_sizing(self):
        """ポジションサイズ計算のテスト"""
        entry_price = 100
        stop_price = 95
        balance = 10000
        
        # ポジションサイズ計算
        size = self.strategy.calculate_position_size(entry_price, stop_price, balance)
        
        # 期待値計算
        risk_per_unit = entry_price - stop_price  # 5
        risk_amount = balance * self.strategy.risk_per_trade  # 100
        expected_size = risk_amount / risk_per_unit  # 20
        
        self.assertEqual(size, expected_size)
    
    def test_should_close_long_position(self):
        """ロングポジションのクローズ判定テスト"""
        # ロングポジションを設定
        self.strategy.update_position('long', 100, 1.0)
        
        # エグジットレベルを設定
        self.strategy.market_data['exit_high'] = 105
        self.strategy.market_data['exit_low'] = 95
        
        # 価格が最安値を下回る
        should_close = asyncio.run(self.strategy.should_close_position(94))
        self.assertTrue(should_close)
        
        # 価格が最安値より上
        should_close = asyncio.run(self.strategy.should_close_position(96))
        self.assertFalse(should_close)
    
    def test_should_close_short_position(self):
        """ショートポジションのクローズ判定テスト"""
        # ショートポジションを設定
        self.strategy.update_position('short', 100, 1.0)
        
        # エグジットレベルを設定
        self.strategy.market_data['exit_high'] = 105
        self.strategy.market_data['exit_low'] = 95
        
        # 価格が最高値を上回る
        should_close = asyncio.run(self.strategy.should_close_position(106))
        self.assertTrue(should_close)
        
        # 価格が最高値より下
        should_close = asyncio.run(self.strategy.should_close_position(104))
        self.assertFalse(should_close)

if __name__ == '__main__':
    unittest.main()