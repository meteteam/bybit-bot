# main.py

import logging
import os
from fastapi import FastAPI, Request
from pybit.unified_trading import HTTP
from dotenv import load_dotenv

# Logger ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(name)

# .env dosyasını yükle
load_dotenv()
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
BASE_URL = os.getenv("BASE_URL", "https://api.bybit.com")

# API anahtarları kontrolü
if not API_KEY or not API_SECRET:
    logger.error("API_KEY veya API_SECRET eksik.")
    raise ValueError("API_KEY veya API_SECRET tanımlı değil.")

# Bybit HTTP oturumu (Unified Trading API v3)
session = HTTP(
    testnet=False,
    api_key=API_KEY,
    api_secret=API_SECRET,
)

# FastAPI uygulaması
app = FastAPI()


def get_usdt_balance() -> float:
    """USDT bakiyesini getirir"""
    try:
        balance_data = session.get_wallet_balance(accountType="UNIFIED", coin="USDT")
        coins = balance_data["result"]["list"][0]["coin"]
        for coin in coins:
            if coin["coin"] == "USDT":
                usdt_balance = float(coin["availableToTrade"])
                logger.info(f"USDT bakiyesi: {usdt_balance}")
                return usdt_balance
    except Exception as e:
        logger.error(f"USDT bakiyesi alınamadı: {e}")
    return 0


def get_market_price(symbol: str) -> float:
    """Piyasa fiyatını alır"""
    try:
        price_data = session.get_ticker(category="linear", symbol=symbol)
        return float(price_data["result"]["list"][0]["lastPrice"])
    except Exception as e:
        logger.error(f"{symbol} için fiyat alınamadı: {e}")
        return 0


def place_order(symbol: str, side: str, qty: float):
    """Piyasa emri ile işlem açar"""
    try:
        result = session.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            order_type="Market",
            qty=qty,
            time_in_force="GoodTillCancel",
        )
        logger.info(f"Emir gönderildi: {result}")
        return result
    except Exception as e:
        logger.error(f"Emir gönderme hatası: {e}")
        return {"error": "Emir gönderilemedi"}


@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    message = data.get("action")
    symbol = data.get("symbol", "ETHUSDT")

    logger.info(f"Gelen sinyal: {message} - {symbol}")

    usdt_balance = get_usdt_balance()
    price = get_market_price(symbol)

    if usdt_balance <= 0 or price <= 0:
        return {"error": "Yetersiz bakiye veya fiyat bilgisi alınamadı."}

    # %50 USDT ile miktar hesaplama
    qty = round((usdt_balance * 0.5) / price, 4)
    logger.info(f"İşlem miktarı: {qty} {symbol}")

    if qty <= 0:
        return {"error": "İşlem miktarı sıfır olamaz."}

    if message == "BUY":
        return place_order(symbol, "Buy", qty)
    elif message in ["SELL", "SHORT_AGAIN"]:
        return place_order(symbol, "Sell", qty)
    elif message == "CLOSE_SHORT":
        return place_order(symbol, "Buy", qty)
    else:
        logger.warning(f"Bilinmeyen sinyal: {message}")
        return {"error": "Geçersiz sinyal"}
