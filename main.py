# main.py
from fastapi import FastAPI
from pydantic import BaseModel
import os
from pybit.unified_trading import HTTP

app = FastAPI()

# API anahtarlarını environment değişkenlerinden al
api_key = os.getenv("BYBIT_API_KEY")
api_secret = os.getenv("BYBIT_API_SECRET")

# Bybit HTTP oturumu
session = HTTP(
    api_key=api_key,
    api_secret=api_secret,
)

# Webhook'tan gelen veriyi temsil eden model
class Signal(BaseModel):
    action: str
    symbol: str

# Cüzdanın %50'si kadar pozisyon açmak için miktarı hesaplayan yardımcı fonksiyon
def get_half_balance(symbol: str) -> float:
    # 1. USDT cüzdan bakiyesini al
    wallet = session.get_wallet_balance(accountType="UNIFIED")["result"]["list"]
    usdt_balance = 0.0
    for asset in wallet[0]["coin"]:
        if asset["coin"] == "USDT":
            usdt_balance = float(asset["availableToTrade"])
            break

    # 2. ETHUSDT fiyatını al
    ticker = session.get_mark_price(category="linear", symbol=symbol)
    mark_price = float(ticker["result"]["markPrice"])

    # 3. %50 bakiye ile miktarı hesapla
    amount_usdt = usdt_balance * 0.5
    qty = round(amount_usdt / mark_price, 4)  # 4 ondalık hassasiyet genellikle yeterlidir
    return qty

@app.post("/webhook")
async def webhook(signal: Signal):
    data = signal.dict()
    action = data.get("action")
    symbol = data.get("symbol")

    if not action or not symbol:
        return {"status": "error", "msg": "Eksik veri"}

    print(f"Gelen sinyal: {action} - {symbol}")

    try:
        qty = get_half_balance(symbol)

        if action == "BUY_PARTIAL":
            session.place_order(
                category="linear",
                symbol=symbol,
                side="Buy",
                order_type="Market",
                qty=qty
            )
        elif action == "SELL_PARTIAL":
            session.place_order(
                category="linear",
                symbol=symbol,
                side="Sell",
                order_type="Market",
                qty=qty
            )
        elif action == "CLOSE_SHORT":
            session.place_order(
                category="linear",
                symbol=symbol,
                side="Buy",
                order_type="Market",
                qty=qty
            )
        elif action == "SHORT_AGAIN":
            session.place_order(
                category="linear",
                symbol=symbol,
                side="Sell",
                order_type="Market",
                qty=qty
            )
        else:
            return {"status": "error", "msg": "Bilinmeyen aksiyon"}

        return {"status": "ok", "qty": qty}

    except Exception as e:
        print("Hata:", str(e))
        return {"status": "error", "msg": str(e)}
