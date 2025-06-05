# main.py
import os
import logging
from fastapi import FastAPI, Request
from pybit.unified_trading import HTTP
from dotenv import load_dotenv

# Logger ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(name)

# .env dosyasını yükle
load_dotenv()

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")

# API anahtarları kontrolü
if not API_KEY or not API_SECRET:
    logger.error("API_KEY veya API_SECRET eksik.")
    raise ValueError("API_KEY veya API_SECRET tanımlı değil.")

# Bybit HTTP session (Unified Account)
session = HTTP(
    testnet=False,
    api_key=API_KEY,
    api_secret=API_SECRET
)

# FastAPI başlat
app = FastAPI()

def get_usdt_balance():
    """
    Kullanıcının USDT bakiyesini getirir (Unified Account içinde kullanılabilir bakiye).
    """
    try:
        result = session.get_wallet_balance(accountType="UNIFIED", coin="USDT")
        balance = float(result["result"]["list"][0]["coin"][0]["availableToTrade"])
        logger.info(f"USDT Available: {balance}")
        return balance
    except Exception as e:
        logger.error(f"USDT bakiyesi alınamadı: {e}")
        return 0

def get_eth_price():
    """
    ETH/USDT son fiyatını getirir.
    """
    try:
        result = session.get_ticker(category="linear", symbol="ETHUSDT")
        return float(result["result"]["list"][0]["lastPrice"])
    except Exception as e:
        logger.error(f"ETH fiyatı alınamadı: {e}")
        return 0

def place_order(symbol: str, side: str, qty: float):
    """
    Market emri ile işlem açar.
    """
    try:
        order = session.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            order_type="Market",
            qty=qty,
            time_in_force="GoodTillCancel",
            reduce_only=False  # Eğer pozisyon kapatılacaksa değiştirebiliriz
        )
        logger.info(f"Emir gönderildi: {order}")
        return order
    except Exception as e:
        logger.error(f"Emir gönderme hatası: {e}")
        return {"error": str(e)}

@app.post("/webhook")
async def webhook(request: Request):
    """
    TradingView'den gelen sinyali işler.
    Mesaj içinde "BUY", "SELL", "SHORT_AGAIN", "CLOSE_SHORT" komutlarını destekler.
    """
    data = await request.json()
    message = data.get("action", "").upper().strip()

    logger.info(f"Gelen sinyal: {message}")

    symbol = "ETHUSDT"
    usdt_balance = get_usdt_balance()
    eth_price = get_eth_price()

    if usdt_balance <= 0 or eth_price <= 0:
        return {"error": "Bakiye veya fiyat alınamadı."}

    # USDT bakiyesinin %50'si kadar ETH hesapla
    eth_qty = round((usdt_balance * 0.5) / eth_price, 4)  # 4 ondalık hassasiyet

    if message == "BUY":
        return place_order(symbol, "Buy", eth_qty)

    elif message == "SELL":
        return place_order(symbol, "Sell", eth_qty)

    elif message == "SHORT_AGAIN":
        return place_order(symbol, "Sell", eth_qty)

    elif message == "CLOSE_SHORT":
        return place_order(symbol, "Buy", eth_qty)

    else:
        logger.warning(f"Tanımsız sinyal: {message}")
        return {"error": "Geçersiz sinyal"}
