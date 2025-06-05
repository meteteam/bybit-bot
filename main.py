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

# Pybit HTTP oturumu
session = HTTP(
    api_key=API_KEY,
    api_secret=API_SECRET
)

# FastAPI uygulaması
app = FastAPI()

def get_usdt_balance():
    """USDT bakiyesini döndürür."""
    try:
        result = session.get_wallet_balance(accountType="UNIFIED", coin="USDT")
        return float(result["result"]["list"][0]["coin"][0]["availableToTrade"])
    except Exception as e:
        logger.error(f"USDT bakiyesi alınamadı: {e}")
        return 0

def get_eth_price():
    """ETH/USDT fiyatını getirir (mark price)."""
    try:
        result = session.get_mark_price(symbol="ETHUSDT", category="linear")
        return float(result["result"]["markPrice"])
    except Exception as e:
        logger.error(f"ETH fiyatı alınamadı: {e}")
        return 0

def place_order(symbol: str, side: str, qty: float):
    """Market emir ile pozisyon açar."""
    try:
        result = session.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            order_type="Market",
            qty=qty,
            time_in_force="GoodTillCancel"
        )
        logger.info(f"Emir gönderildi: {result}")
        return result
    except Exception as e:
        logger.error(f"Emir gönderme hatası: {e}")
        return {"error": str(e)}

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    message = data.get("action", "")
    logger.info(f"Gelen sinyal: {message}")

    usdt_balance = get_usdt_balance()
    eth_price = get_eth_price()

    if usdt_balance <= 0 or eth_price <= 0:
        return {"error": "Yetersiz bakiye veya fiyat bilgisi alınamadı."}

    qty = round((usdt_balance * 0.5) / eth_price, 4)  # %50'lik işlem aç
    logger.info(f"Hesaplanan ETH miktarı: {qty}")

    if message == "BUY":
        return place_order("ETHUSDT", "Buy", qty)
    elif message == "SELL":
        return place_order("ETHUSDT", "Sell", qty)
    else:
        logger.warning(f"Bilinmeyen sinyal: {message}")
        return {"error": "Geçersiz sinyal"}
