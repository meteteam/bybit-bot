# main.py

import os
import logging
from fastapi import FastAPI, Request
from pybit.unified_trading import HTTP

# Logger yapılandırması
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(name)

# Environment değişkenlerini al
API_KEY = os.getenv("API_KEY", "").strip()
API_SECRET = os.getenv("API_SECRET", "").strip()

# Doğrulama
if not API_KEY or not API_SECRET:
    logger.error("API_KEY veya API_SECRET eksik.")
    raise ValueError("API_KEY veya API_SECRET tanımlı değil.")

# Bybit bağlantısı (Unified Trading için)
session = HTTP(
    api_key=API_KEY,
    api_secret=API_SECRET,
)

# FastAPI başlat
app = FastAPI()

# Belirli bir sembol için bakiyenin %50'sini al
def get_half_balance(symbol: str) -> float:
    try:
        asset = symbol.replace("USDT", "")
        balances = session.get_wallet_balance(accountType="UNIFIED")
        total_equity = float(balances["result"]["list"][0]["totalEquity"])
        mark_price = float(session.get_ticker(category="linear", symbol=symbol)["result"]["list"][0]["lastPrice"])
        qty = (total_equity / mark_price) * 0.5
        return round(qty, 4)
    except Exception as e:
        logger.error(f"Bakiye hesaplanırken hata: {e}")
        return 0.0

@app.post("/webhook")
async def webhook(request: Request):
    try:
        data = await request.json()
        signal = data.get("action", "").upper()
        symbol = data.get("symbol", "ETHUSDT")

        logger.info(f"Gelen sinyal: {signal} - {symbol}")

        qty = get_half_balance(symbol)
        if qty == 0.0:
            return {"status": "failed", "reason": "Bakiye alınamadı veya işlem yapılamaz."}

        if signal == "BUY_PARTIAL":
            session.place_order(
                category="linear",
                symbol=symbol,
                side="Buy",
                orderType="Market",
                qty=qty
            )

        elif signal == "SELL_PARTIAL":
            session.place_order(
                category="linear",
                symbol=symbol,
                side="Sell",
                orderType="Market",
                qty=qty
            )

        elif signal == "SHORT_AGAIN":
            session.place_order(
                category="linear",
                symbol=symbol,
                side="Sell",
                orderType="Market",
                qty=qty
            )

        elif signal == "CLOSE_SHORT":
            session.place_order(
                category="linear",
                symbol=symbol,
                side="Buy",
                orderType="Market",
                qty=qty
            )

        else:
            logger.warning(f"Bilinmeyen sinyal: {signal}")
            return {"status": "ignored", "message": "Bilinmeyen sinyal."}

        return {"status": "success", "signal": signal, "qty": qty}

    except Exception as e:
        logger.error(f"Webhook işlemi sırasında hata: {e}")
        return {"status": "error", "detail": str(e)}
