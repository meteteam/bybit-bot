from fastapi import FastAPI
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from pybit.unified_trading import HTTP

load_dotenv()

app = FastAPI()

API_KEY = os.getenv("BYBIT_API_KEY")
API_SECRET = os.getenv("BYBIT_API_SECRET")

session = HTTP(api_key=API_KEY, api_secret=API_SECRET)

# ✅ Signal modeli tanımı (FastAPI'ye veri tipi anlatılır)
class Signal(BaseModel):
    action: str
    symbol: str

# ✅ Webhook endpoint (Request yerine Signal kullanılır!)
@app.post("/webhook")
async def webhook(signal: Signal):
    data = signal.dict()
    action = data.get("action")
    symbol = data.get("symbol")

    if not action or not symbol:
        return {"status": "error", "msg": "Eksik veri"}

    print(f"Gelen sinyal: {action} - {symbol}")

    if action == "BUY_PARTIAL":
        session.place_order(category="linear", symbol=symbol, side="Buy", order_type="Market", qty=0.5)
    elif action == "SELL_PARTIAL":
        session.place_order(category="linear", symbol=symbol, side="Sell", order_type="Market", qty=0.5)
    elif action == "CLOSE_SHORT":
        session.place_order(category="linear", symbol=symbol, side="Buy", order_type="Market", qty=0.5)
    elif action == "SHORT_AGAIN":
        session.place_order(category="linear", symbol=symbol, side="Sell", order_type="Market", qty=0.5)

    return {"status": "ok"}
