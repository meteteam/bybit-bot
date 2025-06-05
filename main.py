def get_eth_balance():
    """USDT bakiyesini getirir (Unified account için)."""
    try:
        balance_data = session.get_wallet_balance(accountType="UNIFIED")
        logger.info(f"Wallet balance raw response: {balance_data}")
        
        # Doğru coin'e ulaşalım (örneğin USDT)
        coins = balance_data["result"]["list"][0]["coin"]
        for coin in coins:
            if coin["coin"] == "USDT":
                usdt_balance = float(coin["availableToTrade"])
                logger.info(f"USDT bakiyesi: {usdt_balance}")
                return usdt_balance
        
        logger.error("USDT coin bulunamadı.")
        return 0
    except Exception as e:
        logger.error(f"USDT bakiyesi alınamadı: {e}")
        return 0


def get_eth_price():
    """ETH/USDT piyasa fiyatını getirir."""
    try:
        tickers = session.get_tickers(category="linear")  # V5 API
        logger.info(f"Tickers response: {tickers}")
        
        for ticker in tickers["result"]["list"]:
            if ticker["symbol"] == "ETHUSDT":
                price = float(ticker["lastPrice"])
                logger.info(f"ETH fiyatı: {price}")
                return price
        
        logger.error("ETHUSDT fiyatı bulunamadı.")
        return None
    except Exception as e:
        logger.error(f"ETH fiyatı alınamadı: {e}")
        return None
