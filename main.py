# main.py

import os
import logging
from fastapi import FastAPI, Request
from pydantic import BaseModel
from dotenv import load_dotenv
from pybit.unified_trading import HTTP

# .env dosyasını yükle
load_dotenv()

# Logging ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(name)

# Bybit API key'leri
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")

if not API_KEY or not API_SECRET:
    logger.error("API_KEY veya API_SECRET eksik.")
    raise ValueError("API key'ler tanımlı değil.")

# Bybit V5 HTTP bağlantısı (Unified Account)
session = HTTP(api_key=API_KEY, api_secret=API_SECRET)

# FastAPI uygulaması
app = FastAPI()

# Webhook JSON verisi için model
class WebhookRequest(BaseModel):
    action: str
    symbol: str = "ETHUSDT"  # default olarak ETHUSDT kullan

# USDT bakiyesini al
def get_usdt_balance() -> float:
    try:
        balance_data = session.get_wallet_balance(accountType="UNIFIED", coin="USDT")
        available = float(balance_data["result"]["list"][0]["coin"][0]["availableToTrade"])
        logger.info(f"USDT bakiyesi: {available}")
        return available
    except Exception as e:
        logger.error(f"Bakiye alınamadı: {e}")
        return 0.0

# ETHUSDT son fiyatını al
def get_eth_price() -> float:
    try:
        ticker = session.get_tickers(category="linear", symbol="ETHUSDT")
        price = float(ticker["result"]["list"][0]["lastPrice"])
        logger.info(f"ETH fiyatı: {price}")
        return price
    except Exception as e:
        logger.error(f"Fiyat alınamadı: {e}")
        return 0.0

# Emir gönder
def place_order(symbol: str, side: str, qty: float):
    try:
        response = session.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            order_type="Market",
            qty=qty,
            time_in_force="GoodTillCancel"
        )
        logger.info(f"Emir gönderildi: {response}")
        return response
    except Exception as e:
        logger.error(f"Emir hatası: {e}")
        return {"error": str(e)}

# Ana webhook endpoint
@app.post("/webhook")
async def webhook(payload: WebhookRequest):
    action = payload.action.upper()
    symbol = payload.symbol.upper()

    logger.info(f"Gelen sinyal: {action}")

    # Bakiye ve fiyatı al
    usdt = get_usdt_balance()
    price = get_eth_price()

    if usdt == 0 or price == 0:
        return {"error": "Bakiye veya fiyat alınamadı."}

    qty = round(usdt / price, 4)  # %100 bakiye ile pozisyon

    if qty <= 0:
        return {"error": "Geçersiz miktar"}

    # Pozisyon yönüne göre işlem
    if action == "FULL_LONG" or action == "50_RE_LONG":
        return place_order(symbol, "Buy", qty)

    elif action == "FULL_SHORT" or action == "50_RE_SHORT":
        return place_order(symbol, "Sell", qty)

    elif action == "50_LONG_CLOSE" or action == "FULL_LONG_CLOSE":
        return place_order(symbol, "Sell", round(qty / 2, 4) if action == "50_LONG_CLOSE" else qty)

    elif action == "50_SHORT_CLOSE" or action == "FULL_SHORT_CLOSE":
        return place_order(symbol, "Buy", round(qty / 2, 4) if action == "50_SHORT_CLOSE" else qty)

    else:
        logger.warning(f"Bilinmeyen sinyal: {action}")
        return {"error": "Geçersiz sinyal"}
