#!/usr/bin/env python3
"""
仮想通貨自動取引ボット
pybottersを使用したBybit取引
"""
import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from loguru import logger
import pybotters
from dataclasses import dataclass, asdict
import aiofiles
import os
from dotenv import load_dotenv

# 環境変数読み込み
load_dotenv()

@dataclass
class Position:
    """ポジション情報"""
    symbol: str
    side: str  # 'Buy' or 'Sell'
    size: float
    entry_price: float
    timestamp: datetime
    order_id: Optional[str] = None
    
    def unrealized_pnl(self, current_price: float) -> float:
        """未実現損益を計算"""
        if self.side == 'Buy':
            return (current_price - self.entry_price) * self.size
        else:
            return (self.entry_price - current_price) * self.size
    
    def unrealized_pnl_pct(self, current_price: float) -> float:
        """未実現損益率を計算"""
        if self.side == 'Buy':
            return ((current_price - self.entry_price) / self.entry_price) * 100
        else:
            return ((self.entry_price - current_price) / self.entry_price) * 100

@dataclass
class OrderResult:
    """注文結果"""
    success: bool
    order_id: Optional[str] = None
    message: Optional[str] = None
    filled_qty: Optional[float] = None
    avg_price: Optional[float] = None

class BybitTradingBot:
    """Bybit自動取引ボット"""
    
    def __init__(self):
        # API認証情報
        self.api_key = os.getenv('API_KEY')
        self.api_secret = os.getenv('API_SECRET')
        
        # 取引設定
        self.symbol = os.getenv('TRADING_PAIR', 'BTCUSDT').replace('/', '')
        self.trade_amount_usdt = float(os.getenv('TRADE_AMOUNT', '10'))
        self.max_position_usdt = float(os.getenv('MAX_POSITION_SIZE', '100'))
        
        # 戦略パラメータ
        self.fast_ma_period = int(os.getenv('FAST_MA_PERIOD', '10'))
        self.slow_ma_period = int(os.getenv('SLOW_MA_PERIOD', '30'))
        self.take_profit_pct = float(os.getenv('TAKE_PROFIT', '2.0'))
        self.stop_loss_pct = float(os.getenv('STOP_LOSS', '1.0'))
        
        # 実行設定
        self.interval_seconds = int(os.getenv('INTERVAL_SECONDS', '60'))
        self.is_paper_trading = os.getenv('BOT_MODE', 'paper_trading') == 'paper_trading'
        
        # 内部状態
        self.positions: Dict[str, Position] = {}
        self.price_history: List[float] = []
        self.running = False
        self.ws_data = {}
        
        # ロガー設定
        self._setup_logger()
        
    def _setup_logger(self):
        """ロガーの設定"""
        log_level = os.getenv('LOG_LEVEL', 'INFO')
        logger.remove()
        logger.add(
            "logs/bot_{time:YYYY-MM-DD}.log",
            rotation="1 day",
            retention="30 days",
            level=log_level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
        )
        logger.add(
            lambda msg: print(msg),
            level=log_level,
            format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}"
        )
    
    async def initialize(self, client: pybotters.Client):
        """ボットの初期化"""
        logger.info(f"Initializing bot for {self.symbol}")
        logger.info(f"Mode: {'PAPER TRADING' if self.is_paper_trading else 'LIVE TRADING'}")
        logger.info(f"Trade amount: {self.trade_amount_usdt} USDT")
        
        # アカウント情報を取得
        account_info = await self.get_account_info(client)
        if account_info:
            balance = float(account_info.get('totalWalletBalance', 0))
            logger.info(f"Account balance: {balance:.2f} USDT")
    
    async def get_account_info(self, client: pybotters.Client) -> Optional[Dict]:
        """アカウント情報を取得"""
        try:
            resp = await client.get(
                'https://api.bybit.com/v5/account/wallet-balance',
                params={'accountType': 'UNIFIED'}
            )
            data = await resp.json()
            
            if data['retCode'] == 0:
                return data['result']['list'][0]
            else:
                logger.error(f"Failed to get account info: {data['retMsg']}")
                return None
        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            return None
    
    async def get_ticker_price(self, client: pybotters.Client) -> Optional[float]:
        """現在価格を取得"""
        try:
            resp = await client.get(
                'https://api.bybit.com/v5/market/tickers',
                params={'category': 'spot', 'symbol': self.symbol}
            )
            data = await resp.json()
            
            if data['retCode'] == 0:
                return float(data['result']['list'][0]['lastPrice'])
            else:
                logger.error(f"Failed to get ticker: {data['retMsg']}")
                return None
        except Exception as e:
            logger.error(f"Error getting ticker: {e}")
            return None
    
    async def get_klines(self, client: pybotters.Client, interval: str = '5', limit: int = 100) -> Optional[pd.DataFrame]:
        """ローソク足データを取得"""
        try:
            resp = await client.get(
                'https://api.bybit.com/v5/market/kline',
                params={
                    'category': 'spot',
                    'symbol': self.symbol,
                    'interval': interval,
                    'limit': limit
                }
            )
            data = await resp.json()
            
            if data['retCode'] == 0:
                klines = data['result']['list']
                df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
                df['timestamp'] = pd.to_datetime(df['timestamp'].astype(int), unit='ms')
                df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
                return df.sort_values('timestamp').reset_index(drop=True)
            else:
                logger.error(f"Failed to get klines: {data['retMsg']}")
                return None
        except Exception as e:
            logger.error(f"Error getting klines: {e}")
            return None
    
    async def place_order(self, client: pybotters.Client, side: str, qty: float, order_type: str = 'Market') -> OrderResult:
        """注文を発注"""
        if self.is_paper_trading:
            # ペーパートレーディング
            logger.info(f"[PAPER] {side} {qty:.6f} {self.symbol} @ Market")
            return OrderResult(
                success=True,
                order_id=f"PAPER_{datetime.now().timestamp()}",
                filled_qty=qty,
                avg_price=await self.get_ticker_price(client)
            )
        
        try:
            # 実際の注文
            order_data = {
                'category': 'spot',
                'symbol': self.symbol,
                'side': side,
                'orderType': order_type,
                'qty': str(qty),
                'marketUnit': 'quoteCoin' if side == 'Buy' else 'baseCoin'
            }
            
            resp = await client.post(
                'https://api.bybit.com/v5/order/create',
                data=order_data
            )
            data = await resp.json()
            
            if data['retCode'] == 0:
                result = data['result']
                logger.info(f"[LIVE] Order placed: {side} {qty:.6f} {self.symbol}, OrderID: {result['orderId']}")
                return OrderResult(
                    success=True,
                    order_id=result['orderId'],
                    message="Order placed successfully"
                )
            else:
                logger.error(f"Order failed: {data['retMsg']}")
                return OrderResult(success=False, message=data['retMsg'])
                
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return OrderResult(success=False, message=str(e))
    
    def calculate_moving_averages(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        """移動平均を計算"""
        fast_ma = df['close'].rolling(window=self.fast_ma_period).mean()
        slow_ma = df['close'].rolling(window=self.slow_ma_period).mean()
        return fast_ma, slow_ma
    
    def detect_ma_cross(self, fast_ma: pd.Series, slow_ma: pd.Series) -> str:
        """移動平均のクロスを検出"""
        if len(fast_ma) < 2 or pd.isna(fast_ma.iloc[-1]) or pd.isna(slow_ma.iloc[-1]):
            return 'hold'
        
        # 現在と前回の値
        fast_curr, fast_prev = fast_ma.iloc[-1], fast_ma.iloc[-2]
        slow_curr, slow_prev = slow_ma.iloc[-1], slow_ma.iloc[-2]
        
        # ゴールデンクロス（買いシグナル）
        if fast_prev <= slow_prev and fast_curr > slow_curr:
            logger.info(f"Golden cross detected: Fast MA ({fast_curr:.2f}) > Slow MA ({slow_curr:.2f})")
            return 'buy'
        
        # デッドクロス（売りシグナル）
        elif fast_prev >= slow_prev and fast_curr < slow_curr:
            logger.info(f"Death cross detected: Fast MA ({fast_curr:.2f}) < Slow MA ({slow_curr:.2f})")
            return 'sell'
        
        return 'hold'
    
    async def execute_strategy(self, client: pybotters.Client):
        """取引戦略を実行"""
        # 価格データを取得
        df = await self.get_klines(client, interval='5', limit=max(self.slow_ma_period * 2, 100))
        if df is None or len(df) < self.slow_ma_period:
            logger.warning("Insufficient data for strategy")
            return
        
        current_price = float(df['close'].iloc[-1])
        logger.info(f"Current price: ${current_price:,.2f}")
        
        # ポジションチェック
        if self.symbol in self.positions:
            position = self.positions[self.symbol]
            pnl_pct = position.unrealized_pnl_pct(current_price)
            pnl_usdt = position.unrealized_pnl(current_price)
            
            logger.info(
                f"Position: {position.side} {position.size:.6f} @ ${position.entry_price:,.2f} | "
                f"PnL: {pnl_pct:+.2f}% (${pnl_usdt:+,.2f})"
            )
            
            # 利確・損切りチェック
            should_close = False
            reason = ""
            
            if pnl_pct >= self.take_profit_pct:
                should_close = True
                reason = f"Take Profit ({pnl_pct:.2f}% >= {self.take_profit_pct}%)"
            elif pnl_pct <= -self.stop_loss_pct:
                should_close = True
                reason = f"Stop Loss ({pnl_pct:.2f}% <= -{self.stop_loss_pct}%)"
            
            if should_close:
                logger.info(f"Closing position: {reason}")
                close_side = 'Sell' if position.side == 'Buy' else 'Buy'
                result = await self.place_order(client, close_side, position.size)
                
                if result.success:
                    del self.positions[self.symbol]
                    logger.info(f"Position closed successfully. Realized PnL: ${pnl_usdt:+,.2f}")
                    await self.save_trade_log(position, current_price, pnl_usdt, reason)
        
        else:
            # ポジションなし - エントリーシグナルをチェック
            fast_ma, slow_ma = self.calculate_moving_averages(df)
            signal = self.detect_ma_cross(fast_ma, slow_ma)
            
            if signal == 'buy':
                # 買いエントリー
                qty = self.trade_amount_usdt / current_price
                result = await self.place_order(client, 'Buy', self.trade_amount_usdt)
                
                if result.success:
                    self.positions[self.symbol] = Position(
                        symbol=self.symbol,
                        side='Buy',
                        size=qty,
                        entry_price=current_price,
                        timestamp=datetime.now(),
                        order_id=result.order_id
                    )
                    logger.info(f"Opened long position: {qty:.6f} {self.symbol} @ ${current_price:,.2f}")
    
    async def save_trade_log(self, position: Position, exit_price: float, pnl: float, reason: str):
        """取引ログを保存"""
        trade_log = {
            'timestamp': datetime.now().isoformat(),
            'symbol': position.symbol,
            'side': position.side,
            'size': position.size,
            'entry_price': position.entry_price,
            'exit_price': exit_price,
            'pnl_usdt': pnl,
            'pnl_pct': ((exit_price - position.entry_price) / position.entry_price) * 100,
            'reason': reason,
            'mode': 'paper' if self.is_paper_trading else 'live'
        }
        
        log_file = 'logs/trades.json'
        
        # 既存のログを読み込み
        trades = []
        if os.path.exists(log_file):
            async with aiofiles.open(log_file, 'r') as f:
                content = await f.read()
                if content:
                    trades = json.loads(content)
        
        # 新しい取引を追加
        trades.append(trade_log)
        
        # ファイルに保存
        os.makedirs('logs', exist_ok=True)
        async with aiofiles.open(log_file, 'w') as f:
            await f.write(json.dumps(trades, indent=2))
    
    async def run_bot(self):
        """ボットのメインループ"""
        self.running = True
        
        async with pybotters.Client(apis={'bybit': [self.api_key, self.api_secret]}) as client:
            # 初期化
            await self.initialize(client)
            
            # メインループ
            while self.running:
                try:
                    await self.execute_strategy(client)
                    await asyncio.sleep(self.interval_seconds)
                    
                except KeyboardInterrupt:
                    logger.info("Received interrupt signal, shutting down...")
                    self.running = False
                    break
                    
                except Exception as e:
                    logger.error(f"Error in main loop: {e}")
                    await asyncio.sleep(self.interval_seconds * 2)
            
            logger.info("Bot stopped")
    
    def stop(self):
        """ボットを停止"""
        self.running = False

async def main():
    """メイン関数"""
    bot = BybitTradingBot()
    
    try:
        await bot.run_bot()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        bot.stop()

if __name__ == "__main__":
    # イベントループを実行
    asyncio.run(main())