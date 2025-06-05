import asyncio
import os
from typing import Dict, Any
from dotenv import load_dotenv
from loguru import logger
import pybotters
from datetime import datetime

load_dotenv()

class CryptoBot:
    def __init__(self):
        self.api_key = os.getenv('API_KEY')
        self.api_secret = os.getenv('API_SECRET')
        self.symbol = os.getenv('TRADING_PAIR', 'BTCUSDT').replace('/', '')
        self.trade_amount = float(os.getenv('TRADE_AMOUNT', '100'))
        
        self.position = None
        self.last_price = None
        
        logger.add("logs/bot_{time}.log", rotation="1 day", retention="7 days")
        logger.info(f"Bot initialized for {self.symbol}")

    async def get_balance(self, client: pybotters.Client) -> Dict[str, Any]:
        """アカウント残高を取得"""
        try:
            r = await client.get('https://api.bybit.com/v5/account/wallet-balance', 
                               params={'accountType': 'UNIFIED'})
            data = await r.json()
            if data['retCode'] == 0:
                return data['result']['list'][0]
            else:
                logger.error(f"Balance fetch error: {data}")
                return {}
        except Exception as e:
            logger.error(f"Error fetching balance: {e}")
            return {}

    async def get_ticker(self, client: pybotters.Client) -> float:
        """現在価格を取得"""
        try:
            r = await client.get('https://api.bybit.com/v5/market/tickers',
                               params={'category': 'spot', 'symbol': self.symbol})
            data = await r.json()
            if data['retCode'] == 0:
                price = float(data['result']['list'][0]['lastPrice'])
                self.last_price = price
                return price
            else:
                logger.error(f"Ticker fetch error: {data}")
                return 0
        except Exception as e:
            logger.error(f"Error fetching ticker: {e}")
            return 0

    async def place_order(self, client: pybotters.Client, side: str, quantity: float) -> bool:
        """注文を発注"""
        try:
            order_data = {
                'category': 'spot',
                'symbol': self.symbol,
                'side': side.capitalize(),
                'orderType': 'Market',
                'qty': str(quantity),
                'marketUnit': 'baseCoin' if side == 'buy' else 'quoteCoin'
            }
            
            r = await client.post('https://api.bybit.com/v5/order/create', data=order_data)
            data = await r.json()
            
            if data['retCode'] == 0:
                logger.info(f"Order placed successfully: {side} {quantity} {self.symbol}")
                return True
            else:
                logger.error(f"Order failed: {data}")
                return False
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return False

    async def simple_strategy(self, client: pybotters.Client):
        """シンプルな価格追従戦略"""
        # 現在価格を取得
        price = await self.get_ticker(client)
        if price == 0:
            return
        
        # 移動平均を計算（簡易版：過去の価格履歴が必要）
        # ここではデモとして単純なロジックを実装
        
        if self.position is None:
            # ポジションなし → エントリー検討
            logger.info(f"No position. Current price: ${price}")
            # デモ: 常に少量買い
            if self.trade_amount > 0:
                quantity = self.trade_amount / price
                success = await self.place_order(client, 'buy', quantity)
                if success:
                    self.position = {
                        'side': 'long',
                        'entry_price': price,
                        'quantity': quantity
                    }
        else:
            # ポジションあり → 決済検討
            pnl_percent = ((price - self.position['entry_price']) / self.position['entry_price']) * 100
            logger.info(f"Position PnL: {pnl_percent:.2f}%, Current: ${price}, Entry: ${self.position['entry_price']}")
            
            # 利確/損切り判定
            if pnl_percent > 1.0:  # 1%利確
                logger.info("Take profit triggered")
                success = await self.place_order(client, 'sell', self.position['quantity'])
                if success:
                    self.position = None
            elif pnl_percent < -0.5:  # 0.5%損切り
                logger.info("Stop loss triggered")
                success = await self.place_order(client, 'sell', self.position['quantity'])
                if success:
                    self.position = None

    async def run(self):
        """メインループ"""
        async with pybotters.Client(apis={'bybit': [self.api_key, self.api_secret]}) as client:
            logger.info("Bot started")
            
            # 初期残高表示
            balance = await self.get_balance(client)
            if balance:
                logger.info(f"Initial balance: {balance.get('totalWalletBalance', 'N/A')} USDT")
            
            while True:
                try:
                    await self.simple_strategy(client)
                    await asyncio.sleep(10)  # 10秒ごとに実行
                except KeyboardInterrupt:
                    logger.info("Bot stopped by user")
                    break
                except Exception as e:
                    logger.error(f"Error in main loop: {e}")
                    await asyncio.sleep(30)  # エラー時は30秒待機

def main():
    bot = CryptoBot()
    asyncio.run(bot.run())

if __name__ == "__main__":
    main()