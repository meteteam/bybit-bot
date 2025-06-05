# main.py

import os
from fastapi import FastAPI, Request
from pybit.unified_trading import HTTP
from dotenv import load_dotenv
import logging

# Ortam değişkenlerini yükle (.env dosyasından)
load_dotenv()

# Logging yapılandırması
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(name)

# FastAPI uygulaması başlatılıyor
app = FastAPI()

# Bybit API kimlik bilgileri
api_key = os.getenv("BYBIT_API_KEY")
api_secret = os.getenv("BYBIT_API_SECRET")

# Bybit Unified Trading API oturumu oluştur
session = HTTP(
    api_key=api_key,
    api_secret=api_secret,
    testnet=False
)


def get_half_balance(symbol: str) -> float:
    """
    Kullanıcının cüzdanındaki coin bakiyesinin %50'sini döner.
    USDT pariteleri için çalışır.
    """
    try:
        coin_symbol = symbol.replace("USDT", "")
        balance_data = session.get_wallet_balance(accountType="UNIFIED")
        coin_list = balance_data["result"]["list"][0]["coin"]

        coin_info = next((item for item in coin_list if item["coin"] == coin_symbol), None)
        if not coin_info:
            logger.warning(f"{coin_symbol} bakiyesi bulunamadı.")
            return 0.0

        available = float(coin_info.get("availableToTrade") or coin_info.get("availableBalance") or 0)
        qty = available * 0.5
        logger.info(f"Anlık bakiye: {available} {coin_symbol}, İşlem miktarı (50%): {qty}")
        return round(qty, 6)

    except Exception as e:
        logger.error(f"Bakiye alma hatası: {e}")
        return 0.0


@app.post("/webhook")
async def webhook(request: Request):
    """
    TradingView'den gelen POST webhook'u karşılar ve işlemi başlatır.
    """
    try:
        data = await request.json()
        action = data.get("action")
        symbol = data.get("symbol", "ETHUSDT")

        logger.info(f"Gelen sinyal: {action} - {symbol}")

        qty = get_half_balance(symbol)
        if qty == 0:
            logger.warning("İşlem yapılacak bakiye bulunamadı.")
            return {"status": "Bakiye yetersiz"}

        if action == "BUY_PARTIAL":
            session.place_order(category="linear", symbol=symbol, side="Buy", order_type="Market", qty=qty)
            logger.info("Buy emri gönderildi.")

        elif action == "SELL_PARTIAL":
            session.place_order(category="linear", symbol=symbol, side="Sell", order_type="Market", qty=qty)
            logger.info("Sell emri gönderildi.")

        elif action == "CLOSE_SHORT":
            session.place_order(category="linear", symbol=symbol, side="Buy", order_type="Market", qty=qty)
            logger.info("Short pozisyon kapatıldı.")

        elif action == "SHORT_AGAIN":
            session.place_order(category="linear", symbol=symbol, side="Sell", order_type="Market", qty=qty)
            logger.info("Short yeniden açıldı.")

        else:
            logger.warning("Bilinmeyen işlem türü.")
            return {"status": "Hatalı sinyal", "action": action}

        return {"status": "İşlem başarılı", "action": action, "qty": qty}

    except Exception as e:
        logger.error(f"Webhook işlem hatası: {e}")
        return {"status": "Hata", "error": str(e)}
