# main.py
import os
import logging
import math
from fastapi import FastAPI, Request
from pydantic import BaseModel
from pybit.unified_trading import HTTP
from dotenv import load_dotenv

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bybit-bot")

# Ortam değişkenlerini yükle
load_dotenv()
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
if not API_KEY or not API_SECRET:
    raise ValueError("API anahtarları eksik.")

# Bybit unified session
session = HTTP(api_key=API_KEY, api_secret=API_SECRET)

# FastAPI
app = FastAPI()

# Request modeli
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

# USDT bakiyesi çekme
def get_usdt_balance() -> float:
    try:
        wallets = session.get_wallet_balance(accountType="UNIFIED")
        logger.info(f"[DEBUG] Wallets response: {wallets}")
        for coin in wallets["result"]["list"][0]["coin"]:
            if coin["coin"] == "USDT":
                value = coin.get("availableToWithdraw") or coin.get("walletBalance") or "0"
                return float(value) if value not in ["", None] else 0.0
    except Exception as e:
        logger.error(f"Bakiye alınamadı: {e}")
        return 0.0

# Pozisyon miktarını çek
def get_position_qty(symbol: str) -> float:
    try:
        data = session.get_positions(category="linear", symbol=symbol)
        for p in data["result"]["list"]:
            if float(p["size"]) > 0:
                return float(p["size"])
    except Exception as e:
        logger.error(f"{symbol} pozisyon alınamadı: {e}")
    return 0.0

# Sinyal işleme
@app.post("/webhook")
async def webhook(signal: WebhookSignal):
    action = signal.action.upper()
    symbol = signal.symbol.upper()

    logger.info(f"Gelen sinyal: {action}")

    # Fiyat al
    price = get_price(symbol)
    if price <= 0:
        return {"error": "Fiyat alınamadı"}

    # Sinyal grupları
    buy_signals = ["FULL_LONG", "50_RE_LONG"]
    sell_signals = ["FULL_SHORT", "50_RE_SHORT"]
    close_buy_signals = ["FULL_SHORT_CLOSE", "50_SHORT_CLOSE"]
    close_sell_signals = ["FULL_LONG_CLOSE", "50_LONG_CLOSE"]

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
        logger.warning(f"Bilinmeyen sinyal: {action}")
        return {"error": f"Bilinmeyen sinyal: {action}"}

    # Emir miktarını belirle
    if action in buy_signals + sell_signals:
        balance = get_usdt_balance()
        if balance < 5:
            return {"error": "Yetersiz bakiye"}
        portion = 1.0  # FULL için de 50_RE için de tamamı
        qty_raw = (balance * portion) / price

    elif action in close_buy_signals + 
    close_sell_signals:
        position_qty = 
    get_position_qty(symbol)
        if position_qty <= 0:
            return {"error": "Pozisyon yok"}
    
    # Pozisyon yönü kontrolü
        side_check = "Sell" if action in 
    close_sell_signals else "Buy"
        if side != side_check:
            return {"error": f"{side} 
    yönünde pozisyon yok"}

    # %50 veya %100 kapat
        portion = 0.5 if "50_" in action 
    else 1.0
        qty_raw = position_qty * portion
    else:
        return {"error": "Geçersiz sinyal"}

    # Aşağı yuvarla (ETH minimum 0.01)
    qty = math.floor(qty_raw / 0.01) * 0.01
    if qty < 0.01:
        return {"error": f"Min. işlem miktarının altında: {qty}"}

    # Emir gönder
    try:
        order = session.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            order_type="Market",
            qty=qty,
            time_in_force="GoodTillCancel"
        )
        logger.info(f"Emir gönderildi: {order}")
        return {"success": True, "order": order}
    except Exception as e:
        logger.error(f"Emir gönderilemedi: {e}")
        return {"error": str(e)}
