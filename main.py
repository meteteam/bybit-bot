# main.py

import os
import logging
from fastapi import FastAPI, Request
from pydantic import BaseModel
from pybit.unified_trading import HTTP
from dotenv import load_dotenv

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bybit-bot")

# .env yükle
load_dotenv()

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")

if not API_KEY or not API_SECRET:
    logger.error("API_KEY veya API_SECRET eksik.")
    raise ValueError("API_KEY ve API_SECRET tanımlanmalı.")

# Bybit unified hesap bağlantısı
session = HTTP(api_key=API_KEY, api_secret=API_SECRET)

# FastAPI başlat
app = FastAPI()


def get_usdt_balance():
    try:
        balance_data = session.get_wallet_balance(accountType="UNIFIED", coin="USDT")
        logger.info(f"Wallet balance raw response: {balance_data}")
        coins = balance_data["result"]["list"][0]["coin"]
        usdt_info = next((c for c in coins if c["coin"] == "USDT"), None)
        balance = float(usdt_info["availableToWithdraw"])
        logger.info(f"MAIN: USDT bakiyesi: {balance}")
        return balance
    except Exception as e:
        logger.error(f"USDT bakiyesi alınamadı: {e}")
        return 0.0

def get_ethusdt_price():
    try:
        ticker_data = session.get_ticker(category="linear", symbol="ETHUSDT")
        logger.info(f"ETH ticker raw: {ticker_data}")

        result = ticker_data.get("result")
        if isinstance(result, dict):
            price = float(result.get("lastPrice", 0))
        elif isinstance(result, list) and len(result) > 0:
            price = float(result[0].get("lastPrice", 0))
        else:
            raise ValueError("lastPrice bulunamadı")

        logger.info(f"MAIN: ETH fiyatı: {price}")
        return price
    except Exception as e:
        logger.error(f"ETH fiyatı alınamadı: {e}")
        return 0.0
class WebhookRequest(BaseModel):
    action: str
    symbol: str

@app.post("/webhook")
async def webhook(req: WebhookRequest):
    action = req.action
    symbol = req.symbol.upper()

    logger.info(f"Gelen sinyal: {action}")

    balance = get_usdt_balance()
    price = get_ethusdt_price()

    if price == 0:
        return {"error": "ETH fiyatı alınamadı."}

    qty = round((balance * 0.1) / price, 3)
    if qty < 0.001:
        return {"error": "Minimum işlem miktarının altındasınız."}

    # İşlem yönünü belirle
    if action in ["FULL_BUY", "FULL_LONG", "50_RE_LONG"]:
        side = "Buy"
    elif action in ["FULL_SELL", "FULL_SHORT", "50_RE_SHORT"]:
        side = "Sell"
    elif action in ["CLOSE_LONG", "CLOSE_BUY", "FULL_LONG_CLOSE", "50_LONG_CLOSE"]:
        side = "Sell"
    elif action in ["CLOSE_SHORT", "CLOSE_SELL", "FULL_SHORT_CLOSE", "50_SHORT_CLOSE"]:
        side = "Buy"
    else:
        logger.warning(f"Bilinmeyen sinyal: {action}")
        return {"error": f"Bilinmeyen sinyal: {action}"}

    try:
        order = session.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            order_type="Market",
            qty=qty,
            time_in_force="GoodTillCancel"
        )
        logger.info(f"Emir gönderildi: {order}")
        return {"message": "Emir gönderildi", "order": order}
    except Exception as e:
        logger.error(f"Emir gönderilemedi: {e}")
        return {"error": str(e)}
