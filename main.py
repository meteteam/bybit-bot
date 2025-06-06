# main.py
import os
import logging
from fastapi import FastAPI, Request
from pydantic import BaseModel
from pybit.unified_trading import HTTP
from dotenv import load_dotenv

# === .env dosyasını yükle ===
load_dotenv()

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")

# === API KEY kontrolü ===
if not API_KEY or not API_SECRET:
    raise ValueError("API_KEY veya API_SECRET eksik. .env dosyasını kontrol edin.")

# === Logging ayarları ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Bybit V5 unified session ===
session = HTTP(
    api_key=API_KEY,
    api_secret=API_SECRET
)

# === FastAPI uygulaması ===
app = FastAPI()

# === Webhook JSON formatı ===
class WebhookRequest(BaseModel):
    action: str
    symbol: str

# === Kullanılabilir bakiye çek ===
def get_usdt_balance() -> float:
    try:
        response = session.get_wallet_balance(accountType="UNIFIED", coin="USDT")
        logger.info(f"Bakiye verisi: {response}")
        balance = float(response["result"]["list"][0]["coin"][0]["availableBalance"])
        return balance
    except Exception as e:
        logger.error(f"USDT bakiyesi alınamadı: {e}")
        return 0.0

# === ETH/USDT fiyatını çek ===
def get_eth_price() -> float:
    try:
        response = session.get_tickers(category="linear", symbol="ETHUSDT")
        logger.info(f"ETH fiyat verisi: {response}")
        price = float(response["result"]["list"][0]["lastPrice"])
        return price
    except Exception as e:
        logger.error(f"ETH fiyatı alınamadı: {e}")
        return 0.0

# === Market emri gönder ===
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
        logger.info(f"{side} emri gönderildi: {response}")
        return response
    except Exception as e:
        logger.error(f"Emir gönderilemedi: {e}")
        return {"error": str(e)}

# === Webhook endpoint ===
@app.post("/webhook")
async def webhook(req: WebhookRequest):
    action = req.action.upper()
    symbol = req.symbol.upper()
    logger.info(f"Gelen webhook: {action} - {symbol}")

    usdt_balance = get_usdt_balance()
    eth_price = get_eth_price()

    if usdt_balance == 0 or eth_price == 0:
        return {"error": "Bakiyeye veya fiyata ulaşılamadı."}

    position_usdt = usdt_balance * 1.0  # Tüm bakiye ile işlem
    qty = round(position_usdt / eth_price, 4)

    if qty <= 0:
        return {"error": "İşlem yapılacak miktar 0."}

    if action in ["FULL_LONG", "50_RE_LONG"]:
        return place_order(symbol, "Buy", qty)
    elif action in ["FULL_SHORT", "50_RE_SHORT"]:
        return place_order(symbol, "Sell", qty)
    elif action in ["50_LONG_CLOSE", "FULL_LONG_CLOSE"]:
        return place_order(symbol, "Sell", qty)
    elif action in ["50_SHORT_CLOSE", "FULL_SHORT_CLOSE"]:
        return place_order(symbol, "Buy", qty)
    else:
        logger.warning(f"Bilinmeyen action: {action}")
        return {"error": "Geçersiz action"}
