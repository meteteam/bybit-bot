from fastapi import FastAPI
from pydantic import BaseModel
from pybit.unified_trading import HTTP
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI()

API_KEY = os.getenv("BYBIT_API_KEY")
API_SECRET = os.getenv("BYBIT_API_SECRET")

session = HTTP(api_key=API_KEY, api_secret=API_SECRET)

class Signal(BaseModel):
    action: str
    symbol: str

def get_half_balance(symbol: str) -> float:
    """
    Verilen sembole göre USDT cinsinden bakiyeyi çeker ve %50'sini hesaplar.
    """
    # Tüm bakiyeleri çek
    balances = session.get_wallet_balance(accountType="UNIFIED")
    usdt_balance = float(balances["result"]["list"][0]["totalEquity"])
    
    # Sembol fiyatını çek (örneğin ETHUSDT için ETH fiyatı)
    market = session.get_ticker(category="linear", symbol=symbol)
    price = float(market["result"]["list"][0]["lastPrice"])
    
    # USDT'nin %50'siyle alınabilecek coin miktarı
    half_qty = (usdt_balance * 0.5) / price
    return round(half_qty, 3)  # virgülden sonra 3 basamak yeterli

@app.post("/webhook")
async def webhook(signal: Signal):
    action = signal.action
    symbol = signal.symbol.upper()

    if not action or not symbol:
        return {"status": "error", "msg": "Eksik veri"}

    print(f"Gelen sinyal: {action} - {symbol}")

    qty = get_half_balance(symbol)

    if action == "BUY_PARTIAL":
        session.place_order(category="linear", symbol=symbol, side="Buy", order_type="Market", qty=qty)
    elif action == "SELL_PARTIAL":
        session.place_order(category="linear", symbol=symbol, side="Sell", order_type="Market", qty=qty)
    elif action == "CLOSE_SHORT":
        session.place_order(category="linear", symbol=symbol, side="Buy", order_type="Market", qty=qty)
    elif action == "SHORT_AGAIN":
        session.place_order(category="linear", symbol=symbol, side="Sell", order_type="Market", qty=qty)

    return {"status": "ok", "executed_qty": qty}
