# main.py
import os
import logging
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

# Bybit HTTP oturumu (Unified Trading API v5)
session = HTTP(
    api_key=API_KEY,
    api_secret=API_SECRET,
    testnet=False  # True ise testnet; ana hesap için False kullan
)

# FastAPI uygulaması
app = FastAPI()

def get_usdt_balance():
    """USDT bakiyesini getirir (UNIFIED hesap türü)"""
    try:
        balance_data = session.get_wallet_balance(accountType="UNIFIED", coin="USDT")
        balance = float(balance_data["result"]["list"][0]["coin"][0]["availableToTrade"])
        logger.info(f"USDT bakiyesi: {balance}")
        return balance
    except Exception as e:
        logger.error(f"USDT bakiyesi alınamadı: {e}")
        return 0.0

def get_ethusdt_price():
    """ETH/USDT güncel fiyatını alır"""
    try:
        ticker = session.get_tickers(category="linear", symbol="ETHUSDT")
        price = float(ticker["result"]["list"][0]["lastPrice"])
        logger.info(f"ETH fiyatı: {price}")
        return price
    except Exception as e:
        logger.error(f"ETH fiyatı alınamadı: {e}")
        return 0.0

def place_order(symbol: str, side: str, qty: float):
    """Market emri gönderir"""
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
    message = data.get("action")
    logger.info(f"Gelen sinyal: {message}")

    symbol = "ETHUSDT"
    eth_price = get_ethusdt_price()
    usdt_balance = get_usdt_balance()

    if eth_price == 0 or usdt_balance == 0:
        return {"error": "Bakiyeye veya fiyata ulaşılamadı."}

    usd_position_size = usdt_balance * 0.5  # %50 pozisyon
    eth_qty = round(usd_position_size / eth_price, 4)

    if message == "BUY":
        return place_order(symbol, "Buy", eth_qty)
    elif message == "SELL":
        return place_order(symbol, "Sell", eth_qty)
    else:
        logger.warning("Bilinmeyen sinyal.")
        return {"error": "Bilinmeyen sinyal"}
