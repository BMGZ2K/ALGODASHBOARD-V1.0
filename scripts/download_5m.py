import ccxt
import pandas as pd
import time
from datetime import datetime, timedelta
import os

def fetch_ohlcv(symbol, timeframe, since, limit=1000):
    exchange = ccxt.binance()
    all_candles = []
    
    while True:
        try:
            print(f"Fetching {symbol} {timeframe} since {datetime.fromtimestamp(since/1000)}")
            candles = exchange.fetch_ohlcv(symbol, timeframe, since, limit)
            if not candles:
                break
            
            all_candles.extend(candles)
            since = candles[-1][0] + 1
            
            if len(candles) < limit:
                break
                
            time.sleep(exchange.rateLimit / 1000)
            
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)
            
    return all_candles

def save_data(symbol, timeframe, days=60):
    start_date = datetime.now() - timedelta(days=days)
    since = int(start_date.timestamp() * 1000)
    
    data = fetch_ohlcv(symbol, timeframe, since)
    
    if not data:
        print(f"No data found for {symbol}")
        return

    df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    os.makedirs('data', exist_ok=True)
    
    filename = f"data/{symbol.replace('/', '')}_{timeframe}.csv"
    df.to_csv(filename, index=False)
    print(f"Saved {len(df)} rows to {filename}")

if __name__ == "__main__":
    save_data('ETH/USDT', '5m', days=60)
