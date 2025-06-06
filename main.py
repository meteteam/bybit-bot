# main.py

import os
import logging
from fastapi import FastAPI
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

# Bybit V5 HTTP API oturumu
session = HTTP(
    api_key=API_KEY,
    api_secret=API_SECRET
)

# FastAPI başlat
app = FastAPI()

# Request veri modeli
class WebhookRequest(BaseModel):
    action: str

# Bakiye çekme
def get_usdt_balance():
    try:
        balance_data = session.get_wallet_balance(accountType="UNIFIED", coin="USDT")
        logger.info(f"Wallet balance raw response: {balance_data}")
        balance = float(balance_data["result"]["list"][0]["coin"][0]["availableToTrade"])
        logger.info(f"USDT bakiyesi: {balance}")
        return balance
    except Exception as e:
        logger.error(f"Bakiye alınamadı: {e}")
        return 0.0

# Fiyat çekme
def get_ethusdt_price():
    try:
        ticker_data = session.get_tickers(category="linear", symbol="ETHUSDT")
        logger.info(f"Ticker raw response: {ticker_data}")
        price = float(ticker_data["result"]["list"][0]["lastPrice"])
        logger.info(f"ETH fiyatı: {price}")
        return price
    except Exception as e:
        logger.error(f"Fiyat alınamadı: {e}")
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
        logger.info(f"Emir başarıyla gönderildi: {response}")
        return response
    except Exception as e:
        logger.error(f"Emir gönderilemedi: {e}")
        return {"error": str(e)}

# Webhook endpoint
@app.post("/webhook")
async def webhook(payload: WebhookRequest):
    action = payload.action.upper()
    logger.info(f"Gelen sinyal: {action}")

    usdt_balance = get_usdt_balance()
    eth_price = get_ethusdt_price()

    if usdt_balance == 0 or eth_price == 0:
        return {"error": "Bakiye veya fiyat alınamadı."}

    symbol = "ETHUSDT"
    position_usdt = usdt_balance * 0.5
    qty = round(position_usdt / eth_price, 4)

    if qty <= 0:
        return {"error": "Yetersiz bakiye veya fiyat hatası."}

    # İşlem eşlemesi
    if action in ["FULL_LONG", "50_RE_LONG", "BUY", "BUY_PARTIAL"]:
        return place_order(symbol, "Buy", qty)

    elif action in ["FULL_SHORT", "50_RE_SHORT", "SELL", "SELL_PARTIAL"]:
        return place_order(symbol, "Sell", qty)

    elif action in ["FULL_LONG_CLOSE", "50_LONG_CLOSE", "FULL_SHORT_CLOSE", "50_SHORT_CLOSE"]:
        # İşlem kapatma yapılmayacaksa burada log atılabilir
        logger.info(f"Sadece işlem kapanış sinyali alındı: {action} — Aktif pozisyon yok.")
        return {"info": f"Sinyal alındı: {action}, işlem gönderilmedi (sadece kapanış etiketi)."}

    else:
        logger.warning(f"Bilinmeyen sinyal: {action}")
        return {"error": "Geçersiz sinyal"}
