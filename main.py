# main.py

import os
import logging
from fastapi import FastAPI, Request
from pybit.unified_trading import HTTP
from dotenv import load_dotenv

# Logging ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(name)

# Ortam değişkenlerini yükle
load_dotenv()
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")

# API key'ler kontrol ediliyor
if not API_KEY or not API_SECRET:
    logger.error("API_KEY veya API_SECRET eksik.")
    raise ValueError("API_KEY veya API_SECRET tanımlı değil.")

# Bybit Unified API bağlantısı (main account için)
session = HTTP(
    api_key=API_KEY,
    api_secret=API_SECRET
)

# FastAPI app tanımı
app = FastAPI()


def get_eth_balance() -> float:
    """
    Kullanıcının Unified account içindeki USDT bakiyesinden ETH işlem miktarını hesaplar.
    """
    try:
        balance_data = session.get_wallet_balance(accountType="UNIFIED")
        usdt_info = next(
            (item for item in balance_data["result"]["list"][0]["coin"] if item["coin"] == "USDT"), None
        )
        if usdt_info:
            available_usdt = float(usdt_info["availableToTrade"])
            logger.info(f"USDT bakiyesi: {available_usdt}")
            eth_price = get_eth_price()
            if eth_price > 0:
                eth_qty = round((available_usdt / eth_price) * 0.5, 4)
                logger.info(f"İşlem açılacak ETH miktarı: {eth_qty}")
                return eth_qty
            else:
                logger.error("ETH fiyatı alınamadı.")
        else:
            logger.error("USDT bilgisi bulunamadı.")
    except Exception as e:
        logger.error(f"USDT bakiyesi alınamadı: {e}")
    return 0


def get_eth_price() -> float:
    """
    ETH/USDT güncel fiyatını getirir.
    """
    try:
        tickers = session.get_tickers(category="linear")
        for ticker in tickers["result"]["list"]:
            if ticker["symbol"] == "ETHUSDT":
                price = float(ticker["lastPrice"])
                logger.info(f"ETH/USDT fiyatı: {price}")
                return price
    except Exception as e:
        logger.error(f"ETH fiyatı alınamadı: {e}")
    return 0


def place_order(symbol: str, side: str, qty: float):
    """
    Belirtilen sembol ve miktarla piyasa emri gönderir.
    """
    try:
        result = session.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            order_type="Market",
            qty=qty,
            time_in_force="GoodTillCancel"
        )
        logger.info(f"Emir başarıyla gönderildi: {result}")
        return result
    except Exception as e:
        logger.error(f"Emir gönderme hatası: {e}")
        return {"error": str(e)}


@app.post("/webhook")
async def webhook(request: Request):
    """
    TradingView veya benzeri servislerden gelen webhook POST isteğini işler.
    """
    data = await request.json()
    action = data.get("action", "").upper()
    logger.info(f"Gelen sinyal: {action}")

    symbol = "ETHUSDT"
    qty = get_eth_balance()

    if qty <= 0:
        return {"error": "Yetersiz bakiye veya fiyat bilgisi alınamadı."}

    if action in ["BUY", "CLOSE_SHORT"]:
        return place_order(symbol, "Buy", qty)
    elif action in ["SELL", "SHORT_AGAIN"]:
        return place_order(symbol, "Sell", qty)
    else:
        logger.warning(f"Bilinmeyen sinyal: {action}")
        return {"error": "Geçersiz sinyal"}
