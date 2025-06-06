# main.py

import os
import logging
from fastapi import FastAPI, Request
from pydantic import BaseModel
from pybit.unified_trading import HTTP
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

# Logging yapılandırması
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

# Bybit API anahtarları
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")

if not API_KEY or not API_SECRET:
    logger.error("API_KEY veya API_SECRET tanımlı değil.")
    raise ValueError("API_KEY veya API_SECRET eksik.")

# Bybit V5 API oturumu
session = HTTP(
    api_key=API_KEY,
    api_secret=API_SECRET
)

# FastAPI uygulaması
app = FastAPI()


# === Request JSON modeli ===
class WebhookRequest(BaseModel):
    action: str


# === USDT bakiyesi al ===
def get_usdt_balance():
    try:
        balance_data = session.get_wallet_balance(accountType="UNIFIED")
        logger.info(f"Wallet balance raw response: {balance_data}")

        # USDT bilgisi coin listesi içinden filtreleniyor
        coins = balance_data["result"]["list"][0]["coin"]
        usdt_info = next((coin for coin in coins if coin["coin"] == "USDT"), None)

        if usdt_info is None:
            logger.error("USDT bilgisi bulunamadı.")
            return 0.0

        # Mevcut bakiye: availableToWithdraw
        balance = float(usdt_info.get("availableToWithdraw", 0))
        logger.info(f"USDT bakiyesi: {balance}")
        return balance

    except Exception as e:
        logger.error(f"USDT bakiyesi alınamadı: {e}")
        return 0.0


# === ETHUSDT fiyatı al ===
def get_ethusdt_price():
    try:
        ticker = session.get_tickers(category="linear", symbol="ETHUSDT")
        logger.info(f"ETH ticker raw: {ticker}")
        price = float(ticker["result"]["list"][0]["lastPrice"])
        logger.info(f"ETH fiyatı: {price}")
        return price
    except Exception as e:
        logger.error(f"ETH fiyatı alınamadı: {e}")
        return 0.0


# === Market emri gönder ===
def place_order(symbol: str, side: str, qty: float):
    try:
        order = session.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            order_type="Market",
            qty=qty,
            time_in_force="GoodTillCancel"
        )
        logger.info(f"Market emri gönderildi: {order}")
        return order
    except Exception as e:
        logger.error(f"Emir gönderilemedi: {e}")
        return {"error": str(e)}


# === Webhook endpoint ===
@app.post("/webhook")
async def webhook(payload: WebhookRequest):
    action = payload.action.upper()
    logger.info(f"Gelen sinyal: {action}")

    usdt = get_usdt_balance()
    eth_price = get_ethusdt_price()

    if usdt == 0 or eth_price == 0:
        return {"error": "Bakiyeye veya fiyata ulaşılamadı."}

    # %50’lik pozisyon
    position_usdt = usdt * 0.5
    qty = round(position_usdt / eth_price, 4)

    if qty <= 0:
        return {"error": "Pozisyon miktarı geçersiz."}

    symbol = "ETHUSDT"

    if action == "FULL_LONG":
        return place_order(symbol, "Buy", qty)
    elif action == "FULL_SHORT":
        return place_order(symbol, "Sell", qty)
    else:
        logger.warning(f"Bilinmeyen sinyal: {action}")
        return {"error": "Geçersiz sinyal"}
