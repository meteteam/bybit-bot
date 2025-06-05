# main.py

import os
import logging
from fastapi import FastAPI, Request
from pybit.unified_trading import HTTP
from dotenv import load_dotenv

# .env dosyasını yükle (Render'da environment variables kullanılıyor olsa da local için şart)
load_dotenv()

# Logger tanımı
logger = logging.getLogger("main")
logging.basicConfig(level=logging.INFO)

# FastAPI uygulaması
app = FastAPI()

# Bybit API kimlik bilgileri
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")

if not API_KEY or not API_SECRET:
    logger.error("API_KEY veya API_SECRET eksik.")
    raise ValueError("API_KEY veya API_SECRET tanımlı değil.")

# Bybit unified V5 bağlantısı
session = HTTP(
    api_key=API_KEY,
    api_secret=API_SECRET
)

# %50 bakiye ile işlem açma için yardımcı fonksiyon
def get_half_balance(symbol: str) -> float:
    # Hesap bakiyesini al
    balance_data = session.get_wallet_balance(accountType="UNIFIED")
    usdt_balance = float(balance_data['result']['list'][0]['coin'][0]['availableToTrade'])
    
    # Market fiyatını al
    price_data = session.get_ticker(category="linear", symbol=symbol)
    mark_price = float(price_data['result']['list'][0]['lastPrice'])
    
    # %50 bakiye ile alınabilecek miktarı hesapla
    qty = (usdt_balance * 0.5) / mark_price
    return round(qty, 4)


@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    logger.info(f"Gelen sinyal: {data}")

    action = data.get("action")
    symbol = data.get("symbol", "ETHUSDT")

    if not action:
        logger.warning("Geçersiz istek: action parametresi eksik.")
        return {"error": "action parametresi eksik"}

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
            return {"message": f"{symbol} için long pozisyon açıldı: qty={qty}"}

        elif action == "SELL_PARTIAL":
            session.place_order(
                category="linear",
                symbol=symbol,
                side="Sell",
                order_type="Market",
                qty=qty
            )
            return {"message": f"{symbol} için short pozisyon açıldı: qty={qty}"}

        elif action == "CLOSE_LONG":
            session.place_order(
                category="linear",
                symbol=symbol,
                side="Sell",
                order_type="Market",
                qty=qty,
                reduce_only=True
            )
            return {"message": f"{symbol} için long pozisyon kapatıldı: qty={qty}"}

        elif action == "CLOSE_SHORT":
            session.place_order(
                category="linear",
                symbol=symbol,
                side="Buy",
                order_type="Market",
                qty=qty,
                reduce_only=True
            )
            return {"message": f"{symbol} için short pozisyon kapatıldı: qty={qty}"}

        else:
            logger.warning(f"Tanımsız action: {action}")
            return {"error": "Tanımsız action"}

    except Exception as e:
        logger.error(f"Hata oluştu: {e}")
        return {"error": str(e)}
