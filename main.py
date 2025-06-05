# main.py

import logging
import os
from fastapi import FastAPI, Request
from pybit.unified_trading import HTTP
from dotenv import load_dotenv

# Logger yapılandırması
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# .env dosyasını yükle
load_dotenv()

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
BASE_URL = os.getenv("BASE_URL", "https://api.bybit.com")

if not API_KEY or not API_SECRET:
    logger.error("API_KEY veya API_SECRET eksik.")
    raise ValueError("API_KEY veya API_SECRET tanımlı değil.")

# Bybit HTTP (Unified Trading API V5) oturumu
session = HTTP(
    api_key=API_KEY,
    api_secret=API_SECRET,
    endpoint=BASE_URL,
)

# FastAPI uygulaması
app = FastAPI()


def get_usdt_balance() -> float:
    """
    Kullanıcının UNIFIED hesabındaki USDT bakiyesini döner.
    """
    try:
        response = session.get_wallet_balance(accountType="UNIFIED", coin="USDT")
        usdt_balance = float(response["result"]["list"][0]["coin"][0]["availableToTrade"])
        logger.info(f"USDT bakiyesi: {usdt_balance}")
        return usdt_balance
    except Exception as e:
        logger.error(f"USDT bakiyesi alınamadı: {e}")
        return 0.0


def get_eth_price() -> float:
    """
    ETHUSDT için güncel fiyatı getirir (orderbook üzerinden).
    """
    try:
        orderbook = session.get_orderbook(category="linear", symbol="ETHUSDT")
        price = float(orderbook["result"]["a"][0][0])  # En iyi ask fiyatı
        logger.info(f"ETH fiyatı: {price}")
        return price
    except Exception as e:
        logger.error(f"ETH fiyatı alınamadı: {e}")
        return 0.0


def place_market_order(side: str, qty: float):
    """
    Belirtilen miktarda piyasa emri gönderir.
    """
    try:
        order = session.place_order(
            category="linear",
            symbol="ETHUSDT",
            side=side,
            order_type="Market",
            qty=qty,
            time_in_force="GoodTillCancel",
        )
        logger.info(f"{side} emri gönderildi: {order}")
        return order
    except Exception as e:
        logger.error(f"{side} emri gönderilemedi: {e}")
        return {"error": str(e)}


@app.post("/webhook")
async def webhook(request: Request):
    """
    TradingView veya benzeri sistemlerden gelen webhook çağrısını işler.
    """
    data = await request.json()
    action = data.get("action", "").upper()
    logger.info(f"Gelen sinyal: {action}")

    # Mevcut bakiye ve fiyat
    balance = get_usdt_balance()
    eth_price = get_eth_price()

    if balance <= 0 or eth_price <= 0:
        return {"error": "Yetersiz bakiye veya fiyat alınamadı."}

    # %50'lik pozisyon büyüklüğü
    usdt_to_use = balance * 0.5
    qty = round(usdt_to_use / eth_price, 4)  # 4 ondalıklı hassasiyet

    if qty <= 0:
        return {"error": "Hesaplanan miktar geçersiz."}

    # İşlem yönü
    if action in ["BUY", "LONG", "BUY_PARTIAL"]:
        return place_market_order("Buy", qty)
    elif action in ["SELL", "SHORT", "SELL_PARTIAL"]:
        return place_market_order("Sell", qty)
    else:
        return {"error": f"Geçersiz sinyal: {action}"}
