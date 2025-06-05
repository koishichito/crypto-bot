import asyncio
from collections import deque
from typing import Optional
import pandas as pd
import numpy as np
import pybotters
from loguru import logger
from .base import BaseStrategy

class MACrossStrategy(BaseStrategy):
    """移動平均線クロス戦略"""
    
    def __init__(self, symbol: str, trade_amount: float, 
                 fast_period: int = 10, slow_period: int = 30):
        super().__init__(symbol, trade_amount)
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.price_history = deque(maxlen=slow_period)
        self.take_profit = 2.0  # 2%利確
        self.stop_loss = 1.0    # 1%損切り
        
    async def fetch_klines(self, client: pybotters.Client) -> pd.DataFrame:
        """ローソク足データを取得"""
        try:
            r = await client.get(
                'https://api.bybit.com/v5/market/kline',
                params={
                    'category': 'spot',
                    'symbol': self.symbol,
                    'interval': '5',  # 5分足
                    'limit': self.slow_period + 5
                }
            )
            data = await r.json()
            
            if data['retCode'] == 0:
                klines = data['result']['list']
                df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
                df['close'] = df['close'].astype(float)
                df['timestamp'] = pd.to_datetime(df['timestamp'].astype(int), unit='ms')
                return df.sort_values('timestamp')
            else:
                logger.error(f"Klines fetch error: {data}")
                return pd.DataFrame()
        except Exception as e:
            logger.error(f"Error fetching klines: {e}")
            return pd.DataFrame()
    
    async def calculate_signal(self, client: pybotters.Client) -> str:
        """移動平均線クロスに基づくシグナル計算"""
        df = await self.fetch_klines(client)
        if df.empty or len(df) < self.slow_period:
            return 'hold'
        
        # 移動平均を計算
        df['ma_fast'] = df['close'].rolling(window=self.fast_period).mean()
        df['ma_slow'] = df['close'].rolling(window=self.slow_period).mean()
        
        # 最新の値を取得
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        self.market_data = {
            'current_price': latest['close'],
            'ma_fast': latest['ma_fast'],
            'ma_slow': latest['ma_slow']
        }
        
        # クロス判定
        if prev['ma_fast'] <= prev['ma_slow'] and latest['ma_fast'] > latest['ma_slow']:
            logger.info(f"Golden cross detected: Fast MA ({latest['ma_fast']:.2f}) > Slow MA ({latest['ma_slow']:.2f})")
            return 'buy'
        elif prev['ma_fast'] >= prev['ma_slow'] and latest['ma_fast'] < latest['ma_slow']:
            logger.info(f"Death cross detected: Fast MA ({latest['ma_fast']:.2f}) < Slow MA ({latest['ma_slow']:.2f})")
            return 'sell'
        
        return 'hold'
    
    async def should_close_position(self, current_price: float) -> bool:
        """利確・損切り判定"""
        if not self.position:
            return False
        
        pnl = self.get_position_pnl(current_price)
        if pnl is None:
            return False
        
        # 利確チェック
        if pnl >= self.take_profit:
            logger.info(f"Take profit triggered: {pnl:.2f}% >= {self.take_profit}%")
            return True
        
        # 損切りチェック
        if pnl <= -self.stop_loss:
            logger.info(f"Stop loss triggered: {pnl:.2f}% <= -{self.stop_loss}%")
            return True
        
        return False