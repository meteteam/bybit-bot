import os
import math
import logging
from fastapi import FastAPI
from pydantic import BaseModel
from pybit.unified_trading import HTTP
from dotenv import load_dotenv

# Logger ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bybit-bot")

# Ortam değişkenlerini yükle
load_dotenv()
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
if not API_KEY or not API_SECRET:
    raise ValueError("API anahtarları eksik.")

# Bybit HTTP oturumu
session = HTTP(api_key=API_KEY, api_secret=API_SECRET)

# FastAPI
app = FastAPI()

# Webhook veri modeli
class WebhookSignal(BaseModel):
    action: str
    symbol: str

# Fiyat çekme
def get_price(symbol: str) -> float:
    try:
        tickers = session.get_tickers(category="linear", symbol=symbol)
        return float(tickers["result"]["list"][0]["lastPrice"])
    except Exception as e:
        logger.error(f"{symbol} fiyatı alınamadı: {e}")
        return 0.0

# Bakiye çekme
def get_usdt_balance() -> float:
    try:
        wallets = session.get_wallet_balance(accountType="UNIFIED")
        for coin in wallets["result"]["list"][0]["coin"]:
            if coin["coin"] == "USDT":
                val = coin.get("availableToWithdraw") or coin.get("walletBalance") or "0"
                return float(val) if val not in ["", None] else 0.0
    except Exception as e:
        logger.error(f"Bakiye alınamadı: {e}")
        return 0.0

# Pozisyon miktarını ve yönünü çekme
def get_position(symbol: str):
    try:
        data = session.get_positions(category="linear", symbol=symbol)
        for p in data["result"]["list"]:
            size = float(p["size"])
            side = p["side"]  # "Buy" or "Sell"
            if size > 0:
                return size, side
    except Exception as e:
        logger.error(f"{symbol} pozisyon alınamadı: {e}")
    return 0.0, None

# Webhook endpoint
@app.post("/webhook")
async def webhook(signal: WebhookSignal):
    action = signal.action.upper()
    symbol = signal.symbol.upper()
    logger.info(f"Webhook Sinyal alındı: {action}, Symbol: {symbol}")

    price = get_price(symbol)
    if price <= 0:
        return {"error": "Fiyat alınamadı"}

    # Sinyal grupları
    buy_signals = ["FULL_LONG", "50_RE_LONG"]
    sell_signals = ["FULL_SHORT", "50_RE_SHORT"]
    close_buy_signals = ["FULL_SHORT_CLOSE", "50_SHORT_CLOSE"]
    close_sell_signals = ["FULL_LONG_CLOSE", "50_LONG_CLOSE"]

    # Pozisyon bilgisi al
    position_qty, position_side = get_position(symbol)

    # Emir yönü
    if action in buy_signals:
        side = "Buy"
    elif action in sell_signals:
        side = "Sell"
    elif action in close_buy_signals:
        side = "Sell"
    elif action in close_sell_signals:
        side = "Buy"
    else:
        return {"error": f"Bilinmeyen sinyal: {action}"}

    # Pozisyon kontrol mantığı
    if action.startswith("FULL") and (position_side and position_side != side):
        return {"error": f"Zıt yönde pozisyon varken {action} yapılamaz."}

    if action.startswith("50_RE"):
        if position_side != side:
            return {"error": f"{action} yalnızca aynı yön pozisyon varken uygulanabilir."}

    if "CLOSE" in action:
        if not position_side:
            return {"error": f"Pozisyon yok: {action} uygulanamaz."}
        if side != position_side:
            return {"error": f"Zıt yön pozisyon varken {action} uygulanamaz."}

    # Emir miktarını belirle
    if action in buy_signals + sell_signals:
        if action.startswith("50_RE"):
            used_margin = position_qty * price
            total_balance = get_usdt_balance()
            available = max(0.0, total_balance - used_margin)
            if available < 5:
                return {"error": "Kalan bakiye yetersiz"}
            qty_raw = available / price
    else:  # FULL_...
            balance = get_usdt_balance()
            if balance < 5:
                return {"error": "Yetersiz bakiye"}
            qty_raw = balance / price
    elif "CLOSE" in action:
        portion = 0.5 if "50_" in action else 1.0
        qty_raw = position_qty * portion
    else:
        return {"error": "Geçersiz sinyal"}

    qty = math.floor(qty_raw / 0.01) * 0.01
    if qty < 0.01:
        return {"error": f"Min. işlem miktarının altında: {qty}"}

    reduce_only = "CLOSE" in action

    try:
        order = session.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            order_type="Market",
            qty=qty,
            time_in_force="GoodTillCancel",
            reduce_only=reduce_only
        )
        logger.info(f"Emir gönderildi: {order}")
        return {"success": True, "order": order}
    except Exception as e:
        logger.error(f"Emir gönderilemedi: {e}")
        return {"error": str(e)}            
