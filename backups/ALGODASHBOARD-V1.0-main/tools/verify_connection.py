import ccxt
import os
import pandas as pd
from dotenv import load_dotenv

# Load Environment Variables
load_dotenv()

API_KEY = os.getenv('Binanceapikey')
SECRET_KEY = os.getenv('BinanceSecretkey')

def verify():
    print("Connecting to Binance Testnet...")
    exchange = ccxt.binance({
        'apiKey': API_KEY,
        'secret': SECRET_KEY,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'spot', 
            'adjustForTimeDifference': True
        }
    })
    exchange.set_sandbox_mode(True) # Enable Testnet
    
    try:
        # 1. Check Balance
        balance = exchange.fetch_balance()
        print("\n--- Balance ---")
        print(f"USDT: {balance['total']['USDT']}")
        print(f"ETH: {balance['total']['ETH']}")
        print(f"BTC: {balance['total']['BTC']}")
        
        # 2. Check Market Data
        symbol = 'ETH/USDT'
        ticker = exchange.fetch_ticker(symbol)
        print(f"\n--- Market Data ({symbol}) ---")
        print(f"Last Price: {ticker['last']}")
        print(f"Bid: {ticker['bid']}")
        print(f"Ask: {ticker['ask']}")
        
        print("\nSUCCESS: Connection Verified.")
        
    except Exception as e:
        print(f"\nERROR: Connection Failed: {e}")

if __name__ == "__main__":
    verify()
