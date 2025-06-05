"""
ブレイクアウト戦略の実装
直近N期間の高値・安値をブレイクしたタイミングでエントリー
"""
import asyncio
from typing import Optional, Tuple, Dict
import pandas as pd
import numpy as np
import pybotters
from loguru import logger
from .base import BaseStrategy

class BreakoutStrategy(BaseStrategy):
    """ブレイクアウト戦略"""
    
    def __init__(self, symbol: str, trade_amount: float,
                 entry_lookback: int = 20, exit_lookback: int = 10,
                 risk_per_trade: float = 0.01):
        """
        Args:
            symbol: 取引シンボル
            trade_amount: 基本取引金額
            entry_lookback: エントリー判定期間（N）
            exit_lookback: エグジット判定期間（M）
            risk_per_trade: 1トレードあたりのリスク（資産比率）
        """
        super().__init__(symbol, trade_amount)
        self.entry_lookback = entry_lookback
        self.exit_lookback = exit_lookback
        self.risk_per_trade = risk_per_trade
        
        # 直前のトレード結果（タートルフィルタ用）
        self.last_trade_profitable = False
        self.use_turtle_filter = True  # タートルフィルタの有効/無効
        
    async def fetch_klines(self, client: pybotters.Client, limit: int = 100) -> pd.DataFrame:
        """ローソク足データを取得"""
        try:
            # 必要な期間分のデータを取得（エントリー期間の2倍程度）
            required_bars = max(self.entry_lookback * 2, limit)
            
            r = await client.get(
                'https://api.bybit.com/v5/market/kline',
                params={
                    'category': 'spot',
                    'symbol': self.symbol,
                    'interval': '60',  # 1時間足
                    'limit': required_bars
                }
            )
            data = await r.json()
            
            if data['retCode'] == 0:
                klines = data['result']['list']
                df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
                df['timestamp'] = pd.to_datetime(df['timestamp'].astype(int), unit='ms')
                df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
                return df.sort_values('timestamp').reset_index(drop=True)
            else:
                logger.error(f"Klines fetch error: {data}")
                return pd.DataFrame()
        except Exception as e:
            logger.error(f"Error fetching klines: {e}")
            return pd.DataFrame()
    
    def calculate_breakout_levels(self, df: pd.DataFrame, lookback: int) -> Tuple[float, float]:
        """
        指定期間の最高値・最安値を計算
        
        Returns:
            (highest_high, lowest_low)
        """
        if len(df) < lookback:
            return None, None
            
        # 最新の足を除いた過去N本の高値・安値を計算
        recent_highs = df['high'].iloc[-lookback-1:-1]
        recent_lows = df['low'].iloc[-lookback-1:-1]
        
        highest_high = recent_highs.max()
        lowest_low = recent_lows.min()
        
        return highest_high, lowest_low
    
    async def calculate_signal(self, client: pybotters.Client) -> str:
        """
        ブレイクアウトシグナルを計算
        
        Returns:
            'buy', 'sell', 'hold'
        """
        df = await self.fetch_klines(client)
        if df.empty or len(df) < self.entry_lookback + 1:
            return 'hold'
        
        # エントリー用のブレイクアウトレベルを計算
        entry_high, entry_low = self.calculate_breakout_levels(df, self.entry_lookback)
        if entry_high is None or entry_low is None:
            return 'hold'
        
        # 現在価格（最新の終値）
        current_price = df['close'].iloc[-1]
        
        # マーケットデータを更新
        self.market_data = {
            'current_price': current_price,
            'entry_high': entry_high,
            'entry_low': entry_low,
            'last_high': df['high'].iloc[-1],
            'last_low': df['low'].iloc[-1]
        }
        
        # ログ出力
        logger.debug(f"Breakout levels - High: {entry_high:.2f}, Low: {entry_low:.2f}, Current: {current_price:.2f}")
        
        # タートルフィルタ: 直前のトレードが利益で終わった場合、次の同方向シグナルは無視
        if self.use_turtle_filter and self.last_trade_profitable:
            logger.info("Turtle filter active - skipping signal after profitable trade")
            self.last_trade_profitable = False  # フィルタをリセット
            return 'hold'
        
        # ブレイクアウト判定
        if current_price > entry_high:
            logger.info(f"Bullish breakout detected: {current_price:.2f} > {entry_high:.2f}")
            return 'buy'
        elif current_price < entry_low:
            logger.info(f"Bearish breakout detected: {current_price:.2f} < {entry_low:.2f}")
            return 'sell'
        
        return 'hold'
    
    async def should_close_position(self, current_price: float) -> bool:
        """
        ポジションクローズ判定（逆方向ブレイク）
        """
        if not self.position:
            return False
        
        # エグジット用のブレイクアウトレベルが必要
        if 'exit_high' not in self.market_data or 'exit_low' not in self.market_data:
            return False
        
        exit_high = self.market_data['exit_high']
        exit_low = self.market_data['exit_low']
        
        # ポジション方向に応じた判定
        if self.position['side'] == 'long':
            # ロングポジション：価格が直近M期間の最安値を下回ったら決済
            if current_price < exit_low:
                logger.info(f"Long exit signal: {current_price:.2f} < {exit_low:.2f}")
                return True
        else:
            # ショートポジション：価格が直近M期間の最高値を上回ったら決済
            if current_price > exit_high:
                logger.info(f"Short exit signal: {current_price:.2f} > {exit_high:.2f}")
                return True
        
        return False
    
    async def update_exit_levels(self, client: pybotters.Client):
        """
        エグジット用のレベルを更新（ポジション保有中に定期的に呼ぶ）
        """
        df = await self.fetch_klines(client)
        if df.empty or len(df) < self.exit_lookback + 1:
            return
        
        # エグジット用のブレイクアウトレベルを計算
        exit_high, exit_low = self.calculate_breakout_levels(df, self.exit_lookback)
        
        if exit_high is not None and exit_low is not None:
            self.market_data['exit_high'] = exit_high
            self.market_data['exit_low'] = exit_low
            logger.debug(f"Exit levels updated - High: {exit_high:.2f}, Low: {exit_low:.2f}")
    
    def calculate_position_size(self, entry_price: float, stop_price: float, balance: float) -> float:
        """
        リスクベースのポジションサイズ計算
        
        Args:
            entry_price: エントリー価格
            stop_price: ストップ価格（エグジットレベル）
            balance: 現在の残高
            
        Returns:
            ポジションサイズ（数量）
        """
        # 1単位あたりのリスク
        risk_per_unit = abs(entry_price - stop_price)
        
        # 許容損失額
        risk_amount = balance * self.risk_per_trade
        
        # ポジションサイズ
        if risk_per_unit > 0:
            position_size = risk_amount / risk_per_unit
        else:
            # リスクが計算できない場合はデフォルトサイズ
            position_size = self.trade_amount / entry_price
        
        logger.info(f"Position sizing - Risk: ${risk_amount:.2f}, Size: {position_size:.6f}")
        
        return position_size
    
    def update_last_trade_result(self, profitable: bool):
        """
        直前のトレード結果を更新（タートルフィルタ用）
        """
        self.last_trade_profitable = profitable
        logger.info(f"Last trade result updated: {'Profitable' if profitable else 'Loss'}")