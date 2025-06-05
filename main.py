# main.py

import os
import logging
from fastapi import FastAPI, Request
from pybit.unified_trading import HTTP
from dotenv import load_dotenv

# Logger ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(name)

# .env dosyasını yükle
load_dotenv()

# API bilgilerini yükle
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")

# API bilgileri eksikse hata fırlat
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


def get_dynamic_eth_qty(symbol: str) -> float:
    """
    USDT bakiyesinin %50'si kadar ETH miktarı hesaplar.

    ETH/USDT fiyatı alınır ve kullanılabilir USDT ile alım miktarı hesaplanır.
    """
    try:
        # Bakiyeyi getir
        wallet = session.get_wallet_balance(accountType="UNIFIED")
        usdt_info = next((coin for coin in wallet["result"]["list"][0]["coin"] if coin["coin"] == "USDT"), None)
        if not usdt_info:
            logger.error("USDT bakiyesi bulunamadı.")
            return 0

        usdt_balance = float(usdt_info["availableToTrade"])
        logger.info(f"USDT bakiyesi: {usdt_balance}")

        # ETH/USDT fiyatını getir
        ticker = session.get_ticker(category="linear", symbol=symbol)
        price = float(ticker["result"]["list"][0]["lastPrice"])
        logger.info(f"{symbol} fiyatı: {price}")

        # %50'lik pozisyon büyüklüğü
        qty = (usdt_balance * 0.5) / price
        return round(qty, 4)
    except Exception as e:
        logger.error(f"ETH miktarı hesaplanamadı: {e}")
        return 0


def place_order(symbol: str, side: str, qty: float):
    """
    Piyasa emri ile işlem açar.
    """
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
        return {"error": str(e)}


@app.post("/webhook")
async def webhook(request: Request):
    """
    TradingView veya başka bir sistemden gelen webhook'u karşılar.
    """
    data = await request.json()
    action = data.get("action", "").upper()

    logger.info(f"Gelen sinyal: {action}")

    symbol = "ETHUSDT"
    qty = get_dynamic_eth_qty(symbol)

    if qty <= 0:
        return {"error": "Yetersiz bakiye veya fiyat bilgisi alınamadı."}

    if action == "BUY":
        return place_order(symbol, "Buy", qty)
    elif action == "SELL":
        return place_order(symbol, "Sell", qty)
    elif action == "SHORT_AGAIN":
        return place_order(symbol, "Sell", qty)
    elif action == "CLOSE_SHORT":
        return place_order(symbol, "Buy", qty)
    else:
        logger.warning(f"Bilinmeyen sinyal: {action}")
        return {"error": "Geçersiz sinyal"}
