# main.py

import os
import logging
from fastapi import FastAPI, Request
from pydantic import BaseModel
from pybit.unified_trading import HTTP
from dotenv import load_dotenv

# Log ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bybit-bot")

# .env dosyasını yükle
load_dotenv()
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")

if not API_KEY or not API_SECRET:
    logger.error("API_KEY veya API_SECRET eksik.")
    raise ValueError("API_KEY veya API_SECRET tanımlı değil.")

# Bybit unified account için oturum oluştur
session = HTTP(api_key=API_KEY, api_secret=API_SECRET)

# FastAPI örneği başlat
app = FastAPI()


# Webhook isteği modeli
class WebhookRequest(BaseModel):
    action: str
    symbol: str


# USDT bakiyesini al
def get_usdt_balance() -> float:
    try:
        resp = session.get_wallet_balance(accountType="UNIFIED", coin="USDT")
        logger.info(f"Cüzdan yanıtı: {resp}")
        return float(resp["result"]["list"][0]["coin"][0]["walletBalance"])
    except Exception as e:
        logger.error(f"USDT bakiyesi alınamadı: {e}")
        return 0.0


# Fiyat bilgisi al
def get_price(symbol: str) -> float:
    try:
        data = session.get_ticker(category="linear", symbol=symbol)
        logger.info(f"{symbol} fiyat verisi: {data}")
        return float(data["result"]["list"][0]["lastPrice"])
    except Exception as e:
        logger.error(f"{symbol} fiyatı alınamadı: {e}")
        return 0.0


# Action'a göre işlem yönü belirle
def determine_side(action: str) -> str:
    buy_signals = ["FULL_LONG", "50_RE_LONG", "FULL_SHORT_CLOSE", "50_SHORT_CLOSE"]
    sell_signals = ["FULL_SHORT", "50_RE_SHORT", "FULL_LONG_CLOSE", "50_LONG_CLOSE"]

    if action in buy_signals:
        return "Buy"
    elif action in sell_signals:
        return "Sell"
    return ""


# Webhook endpoint
@app.post("/webhook")
async def webhook_handler(payload: WebhookRequest):
    action = payload.action.upper()
    symbol = payload.symbol.upper()

    logger.info(f"Gelen sinyal: {action}")

    side = determine_side(action)
    if not side:
        logger.warning(f"Bilinmeyen sinyal: {action}")
        return {"error": f"Bilinmeyen sinyal: {action}"}

    balance = get_usdt_balance()
    if balance < 5:
        return {"error": "Yetersiz bakiye"}

    price = get_price(symbol)
    if price == 0:
        return {"error": "Fiyat alınamadı"}

    qty = round(balance / price, 3)

    # ETH için minimum 0.01 kontrolü
    if symbol.endswith("ETHUSDT") and qty < 0.01:
        return {"error": f"ETH için min işlem miktarı 0.01, hesaplanan: {qty}"}

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
        return {"success": True, "order": order}
    except Exception as e:
        logger.error(f"Emir gönderilemedi: {e}")
        return {"error": str(e)}
