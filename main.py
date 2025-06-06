# main.py

import os
import logging
from fastapi import FastAPI, Request
from pydantic import BaseModel
from pybit.unified_trading import HTTP
from dotenv import load_dotenv

# Logging ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# .env dosyasını yükle
load_dotenv()
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")

if not API_KEY or not API_SECRET:
    logger.error("API_KEY veya API_SECRET tanımlı değil.")
    raise ValueError("API_KEY veya API_SECRET eksik.")

# Bybit oturumu
session = HTTP(
    api_key=API_KEY,
    api_secret=API_SECRET
)

# FastAPI uygulaması
app = FastAPI()

# Webhook request modeli
class WebhookRequest(BaseModel):
    action: str
    symbol: str

# USDT bakiyesi okuma
def get_usdt_balance():
    try:
        balance_data = session.get_wallet_balance(accountType="UNIFIED", coin="USDT")
        logger.info(f"Wallet balance raw response: {balance_data}")

        coins = balance_data["result"]["list"][0]["coin"]
        usdt_coin = next((item for item in coins if item["coin"] == "USDT"), None)

        if usdt_coin:
            balance = float(usdt_coin.get("availableToTrade") or usdt_coin.get("availableToBalance") or 0.0)
            logger.info(f"USDT bakiyesi: {balance}")
            return balance
        else:
            logger.error("USDT bilgisi bulunamadı.")
            return 0.0
    except Exception as e:
        logger.error(f"USDT bakiyesi alınamadı: {e}")
        return 0.0

# ETH fiyatı alma
def get_ethusdt_price():
    try:
        ticker_data = session.get_tickers(category="linear", symbol="ETHUSDT")
        logger.info(f"Ticker response: {ticker_data}")
        price = float(ticker_data["result"]["list"][0]["lastPrice"])
        logger.info(f"ETH fiyatı: {price}")
        return price
    except Exception as e:
        logger.error(f"ETH fiyatı alınamadı: {e}")
        return 0.0

# Emir gönderme
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
        logger.error(f"Emir gönderilemedi: {e}")
        return {"error": str(e)}

# Webhook endpoint
@app.post("/webhook")
async def webhook(payload: WebhookRequest):
    action = payload.action.upper()
    symbol = payload.symbol.upper()
    logger.info(f"Gelen sinyal: {action}")

    usdt_balance = get_usdt_balance()
    eth_price = get_ethusdt_price()

    if usdt_balance == 0 or eth_price == 0:
        return {"error": "Bakiyeye veya fiyata ulaşılamadı."}

    position_usdt = usdt_balance * 0.5
    qty = round(position_usdt / eth_price, 4)

    if qty <= 0:
        return {"error": "Yetersiz bakiye veya fiyat hatası."}

    if action in ["FULL_LONG", "50_RE_LONG"]:
        return place_order(symbol, "Buy", qty)
    elif action in ["FULL_SHORT", "50_RE_SHORT"]:
        return place_order(symbol, "Sell", qty)
    elif action == "50_LONG_CLOSE":
        return place_order(symbol, "Sell", qty)
    elif action == "50_SHORT_CLOSE":
        return place_order(symbol, "Buy", qty)
    elif action in ["FULL_LONG_CLOSE", "FULL_SHORT_CLOSE"]:
        logger.info("Pozisyon kapatma sinyali geldi, manuel kapama gerekebilir.")
        return {"info": "Kapatma sinyali geldi, borsada pozisyonu manuel kapat."}
    else:
        logger.warning(f"Bilinmeyen sinyal: {action}")
        return {"error": "Geçersiz sinyal"}
