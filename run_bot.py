#!/usr/bin/env python3
"""
Crypto Trading Bot - メインエントリーポイント
"""
import asyncio
import sys
from pathlib import Path
from loguru import logger
import pybotters
from datetime import datetime

# プロジェクトのルートをPythonパスに追加
sys.path.append(str(Path(__file__).parent))

from config import BotConfig
from bot.strategies.ma_cross import MACrossStrategy
from bot.strategies.base import BaseStrategy

class TradingBot:
    def __init__(self, config: BotConfig):
        self.config = config
        self.strategy: BaseStrategy = self._create_strategy()
        self.running = False
        
        # ロガー設定
        logger.remove()
        logger.add(sys.stdout, level=config.log_level)
        logger.add(config.log_file, rotation="1 day", retention="7 days", level=config.log_level)
        
    def _create_strategy(self) -> BaseStrategy:
        """設定に基づいて戦略を作成"""
        if self.config.strategy == 'ma_cross':
            return MACrossStrategy(
                symbol=self.config.symbol,
                trade_amount=self.config.trade_amount,
                fast_period=self.config.fast_ma_period,
                slow_period=self.config.slow_ma_period
            )
        else:
            raise ValueError(f"Unknown strategy: {self.config.strategy}")
    
    async def get_account_info(self, client: pybotters.Client) -> dict:
        """アカウント情報を取得"""
        try:
            r = await client.get('https://api.bybit.com/v5/account/wallet-balance', 
                               params={'accountType': 'UNIFIED'})
            data = await r.json()
            if data['retCode'] == 0:
                return data['result']['list'][0]
            else:
                logger.error(f"Account info error: {data}")
                return {}
        except Exception as e:
            logger.error(f"Error fetching account info: {e}")
            return {}
    
    async def execute_trade(self, client: pybotters.Client, side: str, amount: float) -> bool:
        """取引を実行"""
        if self.config.paper_trading:
            logger.info(f"[PAPER TRADE] {side.upper()} {amount:.6f} {self.config.symbol}")
            return True
        
        try:
            order_data = {
                'category': 'spot',
                'symbol': self.config.symbol,
                'side': side.capitalize(),
                'orderType': 'Market',
                'qty': str(amount),
                'marketUnit': 'quoteCoin' if side == 'buy' else 'baseCoin'
            }
            
            r = await client.post('https://api.bybit.com/v5/order/create', data=order_data)
            data = await r.json()
            
            if data['retCode'] == 0:
                logger.info(f"[REAL TRADE] Order executed: {side} {amount} {self.config.symbol}")
                return True
            else:
                logger.error(f"Order failed: {data}")
                return False
        except Exception as e:
            logger.error(f"Error executing trade: {e}")
            return False
    
    async def get_current_price(self, client: pybotters.Client) -> float:
        """現在価格を取得"""
        try:
            r = await client.get('https://api.bybit.com/v5/market/tickers',
                               params={'category': 'spot', 'symbol': self.config.symbol})
            data = await r.json()
            if data['retCode'] == 0:
                return float(data['result']['list'][0]['lastPrice'])
            return 0
        except Exception as e:
            logger.error(f"Error fetching price: {e}")
            return 0
    
    async def trading_loop(self, client: pybotters.Client):
        """メイン取引ループ"""
        while self.running:
            try:
                current_price = await self.get_current_price(client)
                if current_price == 0:
                    await asyncio.sleep(self.config.interval_seconds)
                    continue
                
                logger.info(f"Current price: ${current_price:,.2f}")
                
                # ポジションチェック
                if self.strategy.position:
                    # ポジションあり - クローズ判定
                    pnl = self.strategy.get_position_pnl(current_price)
                    logger.info(f"Position PnL: {pnl:.2f}%")
                    
                    if await self.strategy.should_close_position(current_price):
                        quantity = self.strategy.position['quantity']
                        success = await self.execute_trade(client, 'sell', quantity)
                        if success:
                            self.strategy.clear_position()
                else:
                    # ポジションなし - エントリー判定
                    signal = await self.strategy.calculate_signal(client)
                    logger.info(f"Strategy signal: {signal}")
                    
                    if signal == 'buy':
                        quantity = self.config.trade_amount / current_price
                        success = await self.execute_trade(client, 'buy', self.config.trade_amount)
                        if success:
                            self.strategy.update_position('long', current_price, quantity)
                
                await asyncio.sleep(self.config.interval_seconds)
                
            except KeyboardInterrupt:
                logger.info("Stopping bot...")
                break
            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                await asyncio.sleep(self.config.interval_seconds)
    
    async def run(self):
        """ボットを実行"""
        self.running = True
        
        async with pybotters.Client(apis={self.config.exchange: [self.config.api_key, self.config.api_secret]}) as client:
            logger.info(f"Starting {self.config.strategy} strategy bot for {self.config.symbol}")
            logger.info(f"Mode: {'PAPER TRADING' if self.config.paper_trading else 'LIVE TRADING'}")
            
            # アカウント情報表示
            account_info = await self.get_account_info(client)
            if account_info:
                balance = account_info.get('totalWalletBalance', 'N/A')
                logger.info(f"Account balance: ${balance}")
            
            # 取引ループ開始
            await self.trading_loop(client)
        
        logger.info("Bot stopped")

def main():
    """メイン関数"""
    try:
        # 設定を読み込み
        config = BotConfig.from_env()
        config.validate()
        
        # ボットを起動
        bot = TradingBot(config)
        asyncio.run(bot.run())
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()