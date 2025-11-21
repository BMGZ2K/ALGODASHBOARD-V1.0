import ccxt
import os
import json
from dotenv import load_dotenv

load_dotenv(override=True)

API_KEY = os.getenv('Binanceapikey', '').strip()
SECRET_KEY = os.getenv('BinanceSecretkey', '').strip()

print("DEBUGGING ACCOUNT DATA STRUCTURE...")

exchange = ccxt.binance({
    'apiKey': API_KEY,
    'secret': SECRET_KEY,
    'options': {'defaultType': 'future'}
})

# Force Demo URL
exchange.urls['api']['fapiPrivate'] = 'https://demo-fapi.binance.com/fapi/v1'

try:
    # Fetch v2 account data - Using relative path to avoid base URL duplication issue
    # The previous error was /fapi/v1/v2/account because ccxt appended v2/account to fapi/v1
    # We need to go up levels or set the correct base
    
    # Hack: Request ../v2/account to traverse up from /fapi/v1
    raw = exchange.request('../v2/account', api='fapiPrivate', method='GET')
    
    # Print specific position data for ETHUSDT
    print("\n--- POSITIONS ---")
    found = False
    for pos in raw['positions']:
        if float(pos['positionAmt']) != 0:
            print(json.dumps(pos, indent=2))
            found = True
            
    if not found:
        print("No open positions found (or amount is 0).")
        # Print first position anyway to see structure
        if raw['positions']:
            print("Example empty position:")
            print(json.dumps(raw['positions'][0], indent=2))

    print("\n--- ASSETS ---")
    for asset in raw['assets']:
        if asset['asset'] == 'USDT':
            print(json.dumps(asset, indent=2))

except Exception as e:
    print(f"Error: {e}")
