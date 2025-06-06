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

# Ortam değişkenlerini yükle
load_dotenv()
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")

if not API_KEY or not API_SECRET:
    logger.error("API_KEY veya API_SECRET tanımlı değil.")
    raise ValueError("API_KEY veya API_SECRET eksik.")

# Bybit Unified API session
session = HTTP(api_key=API_KEY, api_secret=API_SECRET)

# FastAPI instance
app = FastAPI()

# Request veri modeli
class WebhookRequest(BaseModel):
    action: str  # Ör: FULL_LONG
    symbol: str  # Ör: ETHUSDT


# Bakiyeyi çek
def get_usdt_balance() -> float:
    try:
        balance_data = session.get_wallet_balance(accountType="UNIFIED", coin="USDT")
        logger.info(f"Wallet balance raw response: {balance_data}")
        balance = float(balance_data["result"]["list"][0]["coin"][0]["walletBalance"])
        logger.info(f"MAIN: USDT bakiyesi: {balance}")
        return balance
    except Exception as e:
        logger.error(f"USDT bakiyesi alınamadı: {e}")
        return 0.0


# ETH fiyatını çek
def get_price(symbol: str) -> float:
    try:
        ticker = session.get_ticker(category="linear", symbol=symbol)
        logger.info(f"{symbol} ticker raw: {ticker}")
        price = float(ticker["result"]["list"][0]["lastPrice"])
        logger.info(f"MAIN: {symbol} fiyatı: {price}")
        return price
    except Exception as e:
        logger.error(f"Fiyat alınamadı: {e}")
        return 0.0


# Webhook endpoint
@app.post("/webhook")
async def webhook_webhook(payload: WebhookRequest):
    action = payload.action.upper()
    symbol = payload.symbol.upper()

    logger.info(f"Gelen sinyal: {action}")

    if {
  "action": "FULL_LONG",
  "symbol": "ETHUSDT"
}
        usdt_balance = get_usdt_balance()
        if usdt_balance <= 1:
            return {"error": "Yetersiz bakiye."}

        price = get_price(symbol)
        if price <= 0:
            return {"error": "Geçersiz fiyat."}

        # Emir miktarını hesapla (minimum 0.001 olmalı)
        qty = round(usdt_balance / price, 3)
        qty = max(qty, 0.001)

        try:
            response = session.place_order(
                category="linear",
                symbol=symbol,
                side="Buy",
                order_type="Market",
                qty=qty,
                time_in_force="GoodTillCancel"
            )
            logger.info(f"Emir gönderildi: {response}")
            return {"success": True, "order_response": response}
        except Exception as e:
            logger.error(f"Emir gönderilemedi: {e}")
            return {"error": str(e)}

    return {"error": f"Desteklenmeyen aksiyon: {action}"}
