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
                
            # Rate limit respect
            time.sleep(exchange.rateLimit / 1000)
            
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)
            
    return all_candles

def save_data(symbol, timeframe, days=365):
    # Calculate start time
    start_date = datetime.now() - timedelta(days=days)
    since = int(start_date.timestamp() * 1000)
    
    data = fetch_ohlcv(symbol, timeframe, since)
    
    if not data:
        print(f"No data found for {symbol}")
        return

    df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    # Outlier Filtering (Robustness)
    # If High is > 50% higher than Open and Close, likely a bad tick
    # We replace with max of Open/Close * 1.1
    
    df['body_max'] = df[['open', 'close']].max(axis=1)
    mask_high = df['high'] > df['body_max'] * 1.5
    if mask_high.any():
        print(f"⚠️ Detected {mask_high.sum()} outlier highs. Fixing...")
        df.loc[mask_high, 'high'] = df.loc[mask_high, 'body_max'] * 1.1
        
    # Same for Low
    df['body_min'] = df[['open', 'close']].min(axis=1)
    mask_low = df['low'] < df['body_min'] * 0.5
    if mask_low.any():
        print(f"⚠️ Detected {mask_low.sum()} outlier lows. Fixing...")
        df.loc[mask_low, 'low'] = df.loc[mask_low, 'body_min'] * 0.9
        
    # Drop helpers
    df.drop(columns=['body_max', 'body_min'], inplace=True)
    
    # Ensure data directory exists
    os.makedirs('data', exist_ok=True)
    
    filename = f"data/{symbol.replace('/', '')}_{timeframe}.csv"
    df.to_csv(filename, index=False)
    print(f"Saved {len(df)} rows to {filename}")

if __name__ == "__main__":
    symbols = ['BTC/USDT', 'ETH/USDT']
    timeframes = ['15m', '1h']
    
    for symbol in symbols:
        for tf in timeframes:
            save_data(symbol, tf, days=180)
