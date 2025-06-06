# main.py

import os
import logging
from fastapi import FastAPI, Request
from pydantic import BaseModel
from pybit.unified_trading import HTTP
from dotenv import load_dotenv

# Logging ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bybit-bot")

# .env dosyasını yükle
load_dotenv()

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")

if not API_KEY or not API_SECRET:
    logger.error("API_KEY veya API_SECRET tanımlı değil.")
    raise ValueError("API_KEY veya API_SECRET eksik.")

# Bybit Unified hesabı (v5)
session = HTTP(api_key=API_KEY, api_secret=API_SECRET)

# FastAPI başlat
app = FastAPI()


# Request veri modeli
class WebhookRequest(BaseModel):
    action: str
    symbol: str


# Bakiye çekme fonksiyonu
def get_usdt_balance():
    try:
        balance_data = session.get_wallet_balance(accountType="UNIFIED", coin="USDT")
        logger.info(f"Wallet balance raw response: {balance_data}")
        balance_list = balance_data["result"]["list"][0]["coin"]
        usdt_info = next(c for c in balance_list if c["coin"] == "USDT")
        balance = float(usdt_info["walletBalance"])
        logger.info(f"MAIN: USDT bakiyesi: {balance}")
        return balance
    except Exception as e:
        logger.error(f"USDT bakiyesi alınamadı: {e}")
        return 0.0


# Fiyat çekme fonksiyonu
def get_ethusdt_price():
    try:
        ticker_data = session.get_ticker(category="linear", symbol="ETHUSDT")
        logger.info(f"ETH ticker raw: {ticker_data}")
        price = float(ticker_data["result"]["list"][0]["lastPrice"])
        logger.info(f"MAIN: ETH fiyatı: {price}")
        return price
    except Exception as e:
        logger.error(f"ETH fiyatı alınamadı: {e}")
        return 0.0


# Webhook endpoint
@app.post("/webhook")
async def webhook_webhook(req: WebhookRequest):
    action = req.action.upper()
    symbol = req.symbol.upper()

    balance = get_usdt_balance()
    price = get_ethusdt_price()

    # Quantity hesapla (min 10 USD'lik işlem)
    try:
        qty = round((balance * 0.1) / price, 3)
    except Exception as e:
        logger.error(f"Miktar hesaplama hatası: {e}")
        return {"error": f"Miktar hesaplanamadı: {e}"}

    if qty <= 0:
        return {"error": "Hesaplanan miktar sıfır."}

    # Sinyale göre işlem yönünü belirle
    if action in ["FULL_LONG", "50_RE_LONG"]:
        side = "Buy"
    elif action in ["FULL_SHORT", "50_RE_SHORT"]:
        side = "Sell"
    elif action in ["FULL_LONG_CLOSE", "50_LONG_CLOSE"]:
        side = "Sell"
    elif action in ["FULL_SHORT_CLOSE", "50_SHORT_CLOSE"]:
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
        return order
    except Exception as e:
        logger.error(f"Emir gönderilemedi: {e}")
        return {"error": str(e)}
