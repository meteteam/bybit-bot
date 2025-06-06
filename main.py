# main.py
import os
import logging
from fastapi import FastAPI, Request
from pydantic import BaseModel
from pybit.unified_trading import HTTP
from dotenv import load_dotenv

# === LOGGING ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

# === ENV VARS ===
load_dotenv()
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")

if not API_KEY or not API_SECRET:
    logger.error("API_KEY veya API_SECRET tanımlı değil.")
    raise ValueError("API anahtarları eksik!")

# === BYBIT SESSION ===
session = HTTP(api_key=API_KEY, api_secret=API_SECRET)

# === FastAPI APP ===
app = FastAPI()

# === Request Veri Modeli ===
class WebhookRequest(BaseModel):
    action: str


# === USDT Bakiyesi Alma Fonksiyonu ===
def get_usdt_balance() -> float:
    try:
        balance_data = session.get_wallet_balance(accountType="UNIFIED", coin="USDT")
        logger.info(f"Wallet balance raw response: {balance_data}")

        coin_list = balance_data["result"]["list"]
        if not coin_list:
            raise ValueError("Boş coin listesi döndü.")

        coin_info_list = coin_list[0]["coin"]
        usdt_info = next((c for c in coin_info_list if c["coin"] == "USDT"), None)

        if not usdt_info:
            raise ValueError("USDT bilgisi bulunamadı")

        balance = float(usdt_info.get("availableToTrade", 0))
        logger.info(f"USDT bakiyesi: {balance}")
        return balance

    except Exception as e:
        logger.error(f"USDT bakiyesi alınamadı: {e}")
        return 0.0


# === ETHUSDT Fiyatını Getir ===
def get_ethusdt_price() -> float:
    try:
        ticker_data = session.get_tickers(category="linear", symbol="ETHUSDT")
        logger.info(f"Ticker response: {ticker_data}")
        price = float(ticker_data["result"]["list"][0]["lastPrice"])
        logger.info(f"ETH fiyatı: {price}")
        return price
    except Exception as e:
        logger.error(f"ETH fiyatı alınamadı: {e}")
        return 0.0


# === Emir Gönderme Fonksiyonu ===
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
        logger.info(f"Emir başarıyla gönderildi: {response}")
        return response
    except Exception as e:
        logger.error(f"Emir gönderilemedi: {e}")
        return {"error": str(e)}


# === Webhook Endpoint ===
@app.post("/webhook")
async def webhook(payload: WebhookRequest):
    action = payload.action.upper()
    logger.info(f"Gelen sinyal: {action}")

    usdt_balance = get_usdt_balance()
    eth_price = get_ethusdt_price()

    if usdt_balance == 0 or eth_price == 0:
        return {"error": "Bakiyeye veya fiyata ulaşılamadı."}

    position_usdt = usdt_balance * 0.5
    qty = round(position_usdt / eth_price, 4)

    if qty <= 0:
        return {"error": "Yetersiz bakiye veya fiyat hatası."}

    symbol = "ETHUSDT"

    if action in ["FULL_LONG", "BUY"]:
        return place_order(symbol, "Buy", qty)
    elif action in ["FULL_SHORT", "SELL"]:
        return place_order(symbol, "Sell", qty)
    elif action == "FULL_LONG_CLOSE":
        return place_order(symbol, "Sell", qty)
    elif action == "FULL_SHORT_CLOSE":
        return place_order(symbol, "Buy", qty)
    else:
        logger.warning(f"Bilinmeyen sinyal: {action}")
        return {"error": "Geçersiz sinyal."}
