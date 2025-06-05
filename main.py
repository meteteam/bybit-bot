# main.py

import os
import logging
from fastapi import FastAPI, Request
from pybit.unified_trading import HTTP
from dotenv import load_dotenv

# Logging ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# .env yükle
load_dotenv()
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")

if not API_KEY or not API_SECRET:
    logger.error("API_KEY veya API_SECRET tanımlı değil.")
    raise ValueError("API_KEY veya API_SECRET eksik.")

# Bybit V5 API oturumu (endpoint belirtmeye gerek yok)
session = HTTP(
    api_key=API_KEY,
    api_secret=API_SECRET
)

# FastAPI uygulaması
app = FastAPI()

def get_usdt_balance():
    """
    Unified hesap USDT bakiyesini getirir
    """
    try:
        balance_data = session.get_wallet_balance(accountType="UNIFIED", coin="USDT")
        logger.info(f"Wallet balance raw response: {balance_data}")
        balance = float(balance_data["result"]["list"][0]["coin"][0]["availableToTrade"])
        logger.info(f"USDT bakiyesi: {balance}")
        return balance
    except Exception as e:
        logger.error(f"USDT bakiyesi alınamadı: {e}")
        return 0.0

def get_ethusdt_price():
    """
    ETH/USDT son fiyatını getirir (linear market)
    """
    try:
        ticker_data = session.get_tickers(category="linear", symbol="ETHUSDT")
        logger.info(f"Ticker raw response: {ticker_data}")
        price = float(ticker_data["result"]["list"][0]["lastPrice"])
        logger.info(f"ETH fiyatı: {price}")
        return price
    except Exception as e:
        logger.error(f"ETH fiyatı alınamadı: {e}")
        return 0.0

def place_order(symbol: str, side: str, qty: float):
    """
    Market emri gönder
    """
    try:
        response = session.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            order_type="Market",
            qty=qty,
            time_in_force="GoodTillCancel"
        )
        logger.info(f"Emir başarıyla gönderildi: {response}")
        return response
    except Exception as e:
        logger.error(f"Emir gönderilemedi: {e}")
        return {"error": str(e)}

@app.post("/webhook")
async def webhook(request: Request):
    """
    TradingView'den gelen sinyali karşılar ve pozisyon açar/kapatır
    """
    data = await request.json()
    action = data.get("action", "").upper()

    logger.info(f"Gelen sinyal: {action}")

    usdt_balance = get_usdt_balance()
    eth_price = get_ethusdt_price()

    if usdt_balance == 0 or eth_price == 0:
        return {"error": "Bakiyeye veya fiyata ulaşılamadı."}

    # %50'lik pozisyon aç/kapat mantığı
    position_usdt = usdt_balance * 0.5
    qty = round(position_usdt / eth_price, 4)

    if qty <= 0:
        return {"error": "Yetersiz bakiye veya fiyat hatası."}

    symbol = "ETHUSDT"

    if action == "BUY":
        return place_order(symbol, "Buy", qty)
    elif action == "SELL":
        return place_order(symbol, "Sell", qty)
    elif action == "BUY_PARTIAL":
        return place_order(symbol, "Buy", qty)
    elif action == "SELL_PARTIAL":
        return place_order(symbol, "Sell", qty)
    else:
        logger.warning(f"Bilinmeyen sinyal: {action}")
        return {"error": "Geçersiz sinyal"}
