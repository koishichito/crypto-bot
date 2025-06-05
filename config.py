import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

@dataclass
class BotConfig:
    """ボット設定"""
    # API設定
    api_key: str
    api_secret: str
    exchange: str = 'bybit'
    
    # 取引設定
    symbol: str = 'BTCUSDT'
    trade_amount: float = 100.0
    max_position_size: float = 1000.0
    
    # 戦略設定
    strategy: str = 'ma_cross'
    fast_ma_period: int = 10
    slow_ma_period: int = 30
    take_profit: float = 2.0  # %
    stop_loss: float = 1.0    # %
    
    # 実行設定
    interval_seconds: int = 60  # 実行間隔（秒）
    paper_trading: bool = True  # ペーパートレーディングモード
    
    # ログ設定
    log_level: str = 'INFO'
    log_file: str = 'logs/bot_{time}.log'
    
    @classmethod
    def from_env(cls) -> 'BotConfig':
        """環境変数から設定を読み込み"""
        return cls(
            api_key=os.getenv('API_KEY', ''),
            api_secret=os.getenv('API_SECRET', ''),
            exchange=os.getenv('EXCHANGE', 'bybit'),
            symbol=os.getenv('TRADING_PAIR', 'BTC/USDT').replace('/', ''),
            trade_amount=float(os.getenv('TRADE_AMOUNT', '100')),
            max_position_size=float(os.getenv('MAX_POSITION_SIZE', '1000')),
            strategy=os.getenv('STRATEGY', 'ma_cross'),
            fast_ma_period=int(os.getenv('FAST_MA_PERIOD', '10')),
            slow_ma_period=int(os.getenv('SLOW_MA_PERIOD', '30')),
            take_profit=float(os.getenv('TAKE_PROFIT', '2.0')),
            stop_loss=float(os.getenv('STOP_LOSS', '1.0')),
            interval_seconds=int(os.getenv('INTERVAL_SECONDS', '60')),
            paper_trading=os.getenv('BOT_MODE', 'paper_trading') == 'paper_trading',
            log_level=os.getenv('LOG_LEVEL', 'INFO'),
        )
    
    def validate(self) -> bool:
        """設定の妥当性チェック"""
        if not self.api_key or not self.api_secret:
            raise ValueError("API credentials are required")
        
        if self.trade_amount <= 0:
            raise ValueError("Trade amount must be positive")
        
        if self.fast_ma_period >= self.slow_ma_period:
            raise ValueError("Fast MA period must be less than slow MA period")
        
        return True