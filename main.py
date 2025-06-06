import os import logging from fastapi import FastAPI, HTTPException from pydantic import BaseModel from dotenv import load_dotenv from pybit.unified_trading import HTTP from math import floor
.env dosyasını yükle
load_dotenv()
Logging ayarları
logging.basicConfig(level=logging.INFO) logger = logging.getLogger(__name__)
Bybit API key'leri
API_KEY = os.getenv("API_KEY") API_SECRET = os.getenv("API_SECRET")
if not API_KEY or not API_SECRET: logger.error("API_KEY veya API_SECRET eksik.") raise ValueError("API key'ler tanımlı değil.")
Bybit V5 HTTP bağlantısı (Unified Account)
session = HTTP(api_key=API_KEY, api_secret=API_SECRET)
FastAPI uygulaması
app = FastAPI()
Webhook JSON verisi için model
class WebhookRequest(BaseModel): action: str symbol: str = "ETHUSDT" # default olarak ETHUSDT kullan
Miktar ayarlama fonksiyonu
def adjust_qty(qty: float, step: float) -> float: return floor(qty / step) * step
Fiyat alma fonksiyonu
def get_price(symbol: str) -> float: try: ticker = session.get_tickers(category="linear", symbol=symbol) price = float(ticker["result"]["list"][0]["lastPrice"]) logger.info(f"{symbol} fiyatı: {price}") return price except Exception as e: logger.error(f"Fiyat alınamadı: {e}") return 0.0
USDT bakiyesi alma fonksiyonu
def get_usdt_balance() -> float: try: balance_data = session.get_wallet_balance(accountType="UNIFIED", coin="USDT") available = float(balance_data["result"]["list"][0]["coin"][0]["availableToTrade"]) logger.info(f"USDT bakiyesi: {available}") return available except Exception as e: logger.error(f"Bakiye alınamadı: {e}") return 0.0
Emir miktarı hesaplama
def get_qty_for_symbol(symbol: str, usdt: float) -> float: price = get_price(symbol) if price == 0: return 0.0 try: market_info = session.get_instruments_info(category="linear", symbol=symbol) step = float(market_info["result"]["list"][0]["lotSizeFilter"]["qtyStep"]) qty_raw = usdt / price qty = adjust_qty(qty_raw, step) logger.info(f"Hesaplanan miktar: {qty}") return qty except Exception as e: logger.error(f"Market info alınamadı: {e}") return 0.0
Emir gönder
def place_order(symbol: str, side: str, qty: float): try: response = session.place_order( category="linear", symbol=symbol, side=side, order_type="Market", qty=qty, time_in_force="GoodTillCancel" ) logger.info(f"Emir gönderildi: {response}") return response except Exception as e: logger.error(f"Emir hatası: {e}") return {"error": str(e)}
Ana webhook endpoint
@app.post("/webhook") async def webhook(payload: WebhookRequest): action = payload.action.upper() symbol = payload.symbol.upper()
logger.info(f"Gelen sinyal: {action}") usdt = get_usdt_balance() qty = get_qty_for_symbol(symbol, usdt) if usdt == 0 or qty == 0: raise HTTPException(status_code=500, detail="Bakiye veya fiyat alınamadı ya da miktar geçersiz.") # Pozisyon yönüne göre işlem if action == "FULL_LONG" or action == "50_RE_LONG": return place_order(symbol, "Buy", qty) elif action == "FULL_SHORT" or action == "50_RE_SHORT": return place_order(symbol, "Sell", qty) elif action == "50_LONG_CLOSE" or action == "FULL_LONG_CLOSE": close_qty = qty / 2 if action == "50_LONG_CLOSE" else qty return place_order(symbol, "Sell", close_qty) elif action == "50_SHORT_CLOSE" or action == "FULL_SHORT_CLOSE": close_qty = qty / 2 if action == "50_SHORT_CLOSE" else qty return place_order(symbol, "Buy", close_qty) else: logger.warning(f"Bilinmeyen sinyal: {action}") raise HTTPException(status_code=400, detail="Geçersiz sinyal")
