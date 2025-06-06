# main.py
import os
import logging
from fastapi import FastAPI, Request
from pydantic import BaseModel
from pybit.unified_trading import HTTP
from dotenv import load_dotenv

# Logging ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(name)

# .env dosyasını yükle
load_dotenv()
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")

if not API_KEY or not API_SECRET:
    logger.error("API_KEY veya API_SECRET eksik.")
    raise ValueError("API_KEY veya API_SECRET tanımlı değil.")

# Bybit V5 API oturumu
session = HTTP(
    api_key=API_KEY,
    api_secret=API_SECRET,
)

# FastAPI uygulaması
app = FastAPI()

# === Request JSON modeli ===
class WebhookRequest(BaseModel):
    action: str
    symbol: str

# === USDT bakiyesi alma ===
def get_usdt_balance():
    try:
        balance_data = session.get_wallet_balance(accountType="UNIFIED", coin="USDT")
        logger.info(f"Wallet balance raw response: {balance_data}")
        coin_data = balance_data["result"]["list"][0].get("coin", [])
        usdt_info = next((c for c in coin_data if c["coin"] == "USDT"), None)
        if usdt_info is None:
            raise ValueError("USDT bilgisi alınamadı.")
        balance = float(usdt_info["availableToTrade"])
        logger.info(f"USDT bakiyesi: {balance}")
        return balance
    except Exception as e:
        logger.error(f"USDT bakiyesi alınamadı: {e}")
        return 0.0

# === ETH fiyatı alma ===
def get_ethusdt_price():
    try:
        ticker_data = session.get_tickers(category="linear", symbol="ETHUSDT")
        logger.info(f"Ticker raw response: {ticker_data}")
        price = float(ticker_data["result"]["list"][0]["lastPrice"])
        logger.info(f"ETH fiyatı: {price}")
        return price
    except Exception as e:
        logger.error(f"ETH fiyatı alınamadı: {e}")
        return 0.0

# === Emir gönderme ===
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

# === Webhook endpoint ===
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
        return {"error": "Pozisyon açmak için yeterli miktar yok."}

    if action in ["FULL_LONG", "50_RE_LONG", "FULL_SHORT", "50_RE_SHORT"]:
        return place_order(symbol, "Buy" if "LONG" in action else "Sell", qty)

    elif action in ["50_LONG_CLOSE", "FULL_LONG_CLOSE", "50_SHORT_CLOSE", "FULL_SHORT_CLOSE"]:
        return place_order(symbol, "Sell" if "LONG" in action else "Buy", qty)

    else:
        logger.warning(f"Bilinmeyen sinyal: {action}")
        return {"error": "Geçersiz sinyal"}
