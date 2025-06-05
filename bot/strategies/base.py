from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import pybotters
from loguru import logger
import pandas as pd

class BaseStrategy(ABC):
    """戦略の基底クラス"""
    
    def __init__(self, symbol: str, trade_amount: float):
        self.symbol = symbol
        self.trade_amount = trade_amount
        self.position: Optional[Dict[str, Any]] = None
        self.market_data: Dict[str, Any] = {}
        
    @abstractmethod
    async def calculate_signal(self, client: pybotters.Client) -> str:
        """
        売買シグナルを計算
        Returns: 'buy', 'sell', 'hold'
        """
        pass
    
    @abstractmethod
    async def should_close_position(self, current_price: float) -> bool:
        """ポジションをクローズすべきか判断"""
        pass
    
    def update_position(self, side: str, entry_price: float, quantity: float):
        """ポジション情報を更新"""
        self.position = {
            'side': side,
            'entry_price': entry_price,
            'quantity': quantity,
            'timestamp': pd.Timestamp.now()
        }
        logger.info(f"Position updated: {self.position}")
    
    def clear_position(self):
        """ポジションをクリア"""
        self.position = None
        logger.info("Position cleared")
    
    def get_position_pnl(self, current_price: float) -> Optional[float]:
        """現在のPnL（%）を計算"""
        if not self.position:
            return None
        
        entry_price = self.position['entry_price']
        if self.position['side'] == 'long':
            return ((current_price - entry_price) / entry_price) * 100
        else:
            return ((entry_price - current_price) / entry_price) * 100