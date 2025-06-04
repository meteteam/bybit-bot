from fastapi import FastAPI
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from pybit.unified_trading import HTTP

# .env dosyasındaki API_KEY ve SECRET'ı yükle
load_dotenv()

# FastAPI uygulaması başlatılıyor
app = FastAPI()

# Bybit API anahtarlarını ortamdan al
API_KEY = os.getenv("BYBIT_API_KEY")
API_SECRET = os.getenv("BYBIT_API_SECRET")

# Bybit unified trading API oturumu
session = HTTP(api_key=API_KEY, api_secret=API_SECRET)

# Webhook verisi için veri modeli
class Signal(BaseModel):
    action: str
    symbol: str

# Webhook endpoint'i
@app.post("/webhook")
async def webhook(signal: Signal):
    action = signal.action
    symbol = signal.symbol

    print(f"Gelen sinyal: {action} - {symbol}")

    if not action or not symbol:
        return {"status": "error", "msg": "Eksik veri"}

    try:
        if action == "BUY_PARTIAL":
            session.place_order(
                category="linear",
                symbol=symbol,
                side="Buy",
                order_type="Market",
                qty=0.5
            )
        elif action == "SELL_PARTIAL":
            session.place_order(
                category="linear",
                symbol=symbol,
                side="Sell",
                order_type="Market",
                qty=0.5
            )
        elif action == "CLOSE_SHORT":
            session.place_order(
                category="linear",
                symbol=symbol,
                side="Buy",
                order_type="Market",
                qty=0.5
            )
        elif action == "SHORT_AGAIN":
            session.place_order(
                category="linear",
                symbol=symbol,
                side="Sell",
                order_type="Market",
                qty=0.5
            )
        else:
            return {"status": "error", "msg": "Bilinmeyen işlem türü"}

        return {"status": "ok", "action": action}

    except Exception as e:
        return {"status": "error", "msg": str(e)}
