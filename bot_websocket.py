"""
WebSocketを使用したリアルタイム取引ボット
"""
import asyncio
import json
from datetime import datetime
from typing import Dict, Optional
import pybotters
from loguru import logger
import os
from dotenv import load_dotenv
from main import BybitTradingBot, Position, OrderResult

load_dotenv()

class RealtimeTradingBot(BybitTradingBot):
    """WebSocketを使用したリアルタイム取引ボット"""
    
    def __init__(self):
        super().__init__()
        self.orderbook: Dict[str, Dict] = {}
        self.ticker_data: Dict[str, float] = {}
        self.ws_connected = False
        
    async def on_orderbook(self, data: Dict):
        """オーダーブック更新時の処理"""
        if 'data' in data:
            symbol = data['data']['s']
            self.orderbook[symbol] = {
                'bids': data['data']['b'][:5],  # Top 5 bids
                'asks': data['data']['a'][:5],  # Top 5 asks
                'timestamp': datetime.now()
            }
            
            # スプレッドを計算
            if self.orderbook[symbol]['bids'] and self.orderbook[symbol]['asks']:
                best_bid = float(self.orderbook[symbol]['bids'][0][0])
                best_ask = float(self.orderbook[symbol]['asks'][0][0])
                spread = best_ask - best_bid
                spread_pct = (spread / best_ask) * 100
                
                if spread_pct > 0.1:  # スプレッドが0.1%以上の場合は警告
                    logger.warning(f"High spread detected: {spread_pct:.3f}%")
    
    async def on_ticker(self, data: Dict):
        """ティッカー更新時の処理"""
        if 'data' in data:
            symbol = data['data']['symbol']
            self.ticker_data[symbol] = {
                'last_price': float(data['data']['lastPrice']),
                'volume_24h': float(data['data']['volume24h']),
                'turnover_24h': float(data['data']['turnover24h']),
                'price_24h_pct': float(data['data']['price24hPcnt']) * 100
            }
    
    async def on_trade(self, data: Dict):
        """約定データ受信時の処理"""
        if 'data' in data:
            for trade in data['data']:
                price = float(trade['p'])
                size = float(trade['v'])
                side = trade['S']  # Buy or Sell
                
                # 大口取引を検知
                trade_value = price * size
                if trade_value > 10000:  # $10,000以上の取引
                    logger.info(f"🐋 Large trade detected: {side} {size:.4f} @ ${price:,.2f} (${trade_value:,.0f})")
    
    async def subscribe_websocket(self, client: pybotters.Client):
        """WebSocketチャンネルを購読"""
        # WebSocket接続
        ws = await client.ws_connect(
            'wss://stream.bybit.com/v5/public/spot',
            send_json={
                'op': 'subscribe',
                'args': [
                    f'orderbook.50.{self.symbol}',
                    f'publicTrade.{self.symbol}',
                    f'tickers.{self.symbol}'
                ]
            },
            hdlr_json=self.handle_websocket_message
        )
        
        self.ws_connected = True
        logger.info(f"WebSocket connected and subscribed to {self.symbol}")
        
        # WebSocketメッセージを処理
        async for msg in ws:
            pass  # メッセージはhandle_websocket_messageで処理される
    
    async def handle_websocket_message(self, msg: Dict, ws):
        """WebSocketメッセージを処理"""
        topic = msg.get('topic', '')
        
        if 'orderbook' in topic:
            await self.on_orderbook(msg)
        elif 'publicTrade' in topic:
            await self.on_trade(msg)
        elif 'tickers' in topic:
            await self.on_ticker(msg)
        elif msg.get('op') == 'pong':
            logger.debug("Received pong")
        else:
            logger.debug(f"Received message: {msg.get('topic', msg.get('op', 'unknown'))}")
    
    async def execute_realtime_strategy(self, client: pybotters.Client):
        """リアルタイム戦略を実行"""
        # WebSocketデータが利用可能かチェック
        if not self.ticker_data.get(self.symbol):
            return
        
        current_price = self.ticker_data[self.symbol]['last_price']
        volume_24h = self.ticker_data[self.symbol]['volume_24h']
        price_change_24h = self.ticker_data[self.symbol]['price_24h_pct']
        
        logger.info(
            f"📊 {self.symbol}: ${current_price:,.2f} | "
            f"24h: {price_change_24h:+.2f}% | "
            f"Vol: {volume_24h:,.0f}"
        )
        
        # オーダーブックの状態をチェック
        if self.symbol in self.orderbook:
            ob = self.orderbook[self.symbol]
            if ob['bids'] and ob['asks']:
                best_bid = float(ob['bids'][0][0])
                best_ask = float(ob['asks'][0][0])
                mid_price = (best_bid + best_ask) / 2
                
                # ポジション管理（親クラスの戦略を使用）
                await self.execute_strategy(client)
    
    async def run_realtime_bot(self):
        """リアルタイムボットを実行"""
        self.running = True
        
        async with pybotters.Client(apis={'bybit': [self.api_key, self.api_secret]}) as client:
            # 初期化
            await self.initialize(client)
            
            # WebSocket接続タスク
            ws_task = asyncio.create_task(self.subscribe_websocket(client))
            
            # 戦略実行ループ
            while self.running:
                try:
                    if self.ws_connected:
                        await self.execute_realtime_strategy(client)
                    
                    await asyncio.sleep(5)  # 5秒ごとに戦略を評価
                    
                except KeyboardInterrupt:
                    logger.info("Shutting down...")
                    self.running = False
                    break
                except Exception as e:
                    logger.error(f"Error in realtime loop: {e}")
                    await asyncio.sleep(10)
            
            # クリーンアップ
            ws_task.cancel()
            try:
                await ws_task
            except asyncio.CancelledError:
                pass
            
            logger.info("Realtime bot stopped")

async def main():
    """メイン関数"""
    from utils import print_banner
    
    print_banner()
    
    bot = RealtimeTradingBot()
    
    try:
        await bot.run_realtime_bot()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        bot.stop()

if __name__ == "__main__":
    asyncio.run(main())