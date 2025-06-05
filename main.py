# main.py

import os
import logging
from fastapi import FastAPI, Request
from dotenv import load_dotenv
from pybit.unified_trading import HTTP

# Ortam değişkenlerini yükle (.env)
load_dotenv()

# Logger yapılandırması
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API anahtarlarını al
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")

if not API_KEY or not API_SECRET:
    logger.error("API_KEY veya API_SECRET eksik.")
    raise ValueError("API_KEY veya API_SECRET tanımlı değil.")

# Bybit API oturumu (V5 HTTP Unified Trading)
session = HTTP(
    api_key=API_KEY,
    api_secret=API_SECRET,
    testnet=False  # Canlı hesap kullanılıyor
)

# FastAPI uygulaması
app = FastAPI()

def get_eth_balance():
    """Kullanıcının ETHUSDT için mevcut USDT bakiyesini getirir."""
    try:
        balance_data = session.get_wallet_balance(accountType="UNIFIED", coin="USDT")
        usdt_balance = float(balance_data["result"]["list"][0]["coin"][0]["availableToTrade"])
        logger.info(f"USDT bakiyesi: {usdt_balance}")
        return usdt_balance
    except Exception as e:
        logger.error(f"USDT bakiyesi alınamadı: {e}")
        return 0.0

def get_eth_price():
    """ETH/USDT güncel fiyatını getirir."""
    try:
        ticker = session.get_ticker(category="linear", symbol="ETHUSDT")
        price = float(ticker["result"]["list"][0]["lastPrice"])
        logger.info(f"ETH fiyatı: {price}")
        return price
    except Exception as e:
        logger.error(f"ETH fiyatı alınamadı: {e}")
        return None

def place_order(symbol: str, side: str, qty: float):
    """Market emri gönderir (kaldıraçlı ETH/USDT işlemi)."""
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
        logger.error(f"Emir gönderilemedi: {e}")
        return {"error": str(e)}

@app.post("/webhook")
async def webhook(request: Request):
    """TradingView veya manuel test için webhook endpoint."""
    data = await request.json()
    action = data.get("action", "").upper()
    logger.info(f"Gelen sinyal: {action}")

    symbol = "ETHUSDT"
    eth_price = get_eth_price()
    usdt_balance = get_eth_balance()

    if not eth_price or usdt_balance <= 5:
        return {"error": "Yetersiz bakiye veya fiyat alınamadı."}

    # %50 USDT ile işlem açılır
    usdt_to_use = usdt_balance * 0.5
    qty = round(usdt_to_use / eth_price, 4)  # 4 ondalık hassasiyet

    if qty <= 0:
        return {"error": "Hesaplanan miktar sıfır veya negatif."}

    if action in {"BUY", "CLOSE_SHORT"}:
        return place_order(symbol, "Buy", qty)
    elif action in {"SELL", "SHORT", "SHORT_AGAIN"}:
        return place_order(symbol, "Sell", qty)
    else:
        logger.warning(f"Bilinmeyen sinyal: {action}")
        return {"error": "Geçersiz sinyal."}
