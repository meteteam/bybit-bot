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

# .env dosyasını yükle
load_dotenv()

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")

if not API_KEY or not API_SECRET:
    logger.error("API_KEY veya API_SECRET tanımlı değil.")
    raise ValueError("API_KEY veya API_SECRET eksik.")

# Bybit Unified hesap (v5)
session = HTTP(api_key=API_KEY, api_secret=API_SECRET)

# FastAPI başlat
app = FastAPI()

# -------------------------------
# MODELLER
# -------------------------------
class WebhookRequest(BaseModel):
    action: str


# -------------------------------
# Yardımcı Fonksiyonlar
# -------------------------------

def get_usdt_balance():
    try:
        balance_data = session.get_wallet_balance(accountType="UNIFIED")
        logger.info(f"Wallet balance raw response: {balance_data}")

        coins = balance_data["result"]["list"][0]["coin"]

        usdt_info = next((c for c in coins if c["coin"] == "USDT"), None)

        if usdt_info is None:
            logger.error("USDT bulunamadı.")
            return 0.0

        raw_balance = usdt_info.get("walletBalance", "0")
        try:
            balance = float(raw_balance)
        except ValueError:
            logger.error(f"walletBalance float dönüşüm hatası: {raw_balance}")
            return 0.0

        logger.info(f"MAIN: USDT bakiyesi: {balance}")
        return balance

    except Exception as e:
        logger.error(f"Bakiye verisi alınamadı: {e}")
        return 0.0


def get_eth_price() -> float:
    """
    ETH/USDT güncel fiyatını getirir
    """
    try:
        ticker = session.get_tickers(category="linear", symbol="ETHUSDT")
        logger.info(f"ETH ticker raw: {ticker}")
        price = float(ticker["result"]["list"][0]["lastPrice"])
        logger.info(f"MAIN: ETH fiyatı: {price}")
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
        logger.info(f"Emir gönderildi: {response}")
        return response
    except Exception as e:
        logger.error(f"Emir gönderilemedi: {e}")
        return {"error": str(e)}


# -------------------------------
# Webhook Endpoint
# -------------------------------
@app.post("/webhook")
async def webhook(request: WebhookRequest):
    """
    TradingView'den gelen webhook POST isteğini işler
    """
    action = request.action.upper()
    logger.info(f"Gelen sinyal: {action}")

    usdt_balance = get_usdt_balance()
    eth_price = get_eth_price()

    if usdt_balance == 0 or eth_price == 0:
        return {"error": "Bakiyeye veya fiyata ulaşılamadı."}

    position_usdt = usdt_balance * 0.5
    qty = round(position_usdt / eth_price, 4)

    if qty <= 0:
        return {"error": "Pozisyon miktarı sıfır."}

    if action in ["FULL_LONG", "50_RE_LONG"]:
        return place_order("ETHUSDT", "Buy", qty)
    elif action in ["FULL_SHORT", "50_RE_SHORT"]:
        return place_order("ETHUSDT", "Sell", qty)
    elif action in ["50_LONG_CLOSE", "FULL_LONG_CLOSE"]:
        return place_order("ETHUSDT", "Sell", qty)
    elif action in ["50_SHORT_CLOSE", "FULL_SHORT_CLOSE"]:
        return place_order("ETHUSDT", "Buy", qty)
    else:
        logger.warning(f"Bilinmeyen işlem tipi: {action}")
        return {"error": f"Geçersiz sinyal: {action}"}
