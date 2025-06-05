# main.py
import logging
import os
from fastapi import FastAPI, Request
from pybit.unified_trading import HTTP
from dotenv import load_dotenv

# Logger ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# .env dosyasını yükle
load_dotenv()

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")

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


def get_eth_balance():
    """ETH bakiyesini getirir"""
    try:
        balance_data = session.get_wallet_balance(accountType="UNIFIED", coin="ETH")
        eth_balance = float(balance_data["result"]["list"][0]["coin"][0]["availableToTrade"])
        logger.info(f"ETH bakiyesi: {eth_balance}")
        return eth_balance
    except Exception as e:
        logger.error(f"ETH bakiyesi alınamadı: {e}")
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
        return None


@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    message = data.get("action") or ""

    logger.info(f"Gelen sinyal: {message}")

    symbol = "ETHUSDT"
    qty = round(get_eth_balance() * 0.5, 4)  # %50'lik pozisyon, 4 ondalık hassasiyet

    if qty <= 0:
        return {"error": "Yetersiz bakiye"}

    if message == "BUY":
        return place_order(symbol, "Buy", qty)
    elif message == "SELL":
        return place_order(symbol, "Sell", qty)
    elif message == "SHORT_AGAIN":
        return place_order(symbol, "Sell", qty)
    elif message == "CLOSE_SHORT":
        return place_order(symbol, "Buy", qty)
    else:
        logger.warning(f"Bilinmeyen sinyal: {message}")
        return {"error": "Geçersiz sinyal"}
