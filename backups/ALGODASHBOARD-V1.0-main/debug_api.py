import ccxt
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('Binanceapikey')
secret_key = os.getenv('BinanceSecretkey')

exchange = ccxt.binance({
    'apiKey': api_key,
    'secret': secret_key,
    'options': {'defaultType': 'future'}
})
exchange.set_sandbox_mode(True)

print("Testing fetch_balance({'type': 'future'})...")
try:
    bal = exchange.fetch_balance({'type': 'future'})
    print("Success fetch_balance!")
    print(f"USDT: {bal['total']['USDT']}")
except Exception as e:
    print(f"Error fetch_balance: {e}")

print("\nTesting fapiPrivateGetAccount...")
try:
    acc = exchange.fapiPrivateGetAccount()
    print("Success fapiPrivateGetAccount!")
except Exception as e:
    print(f"Error fapiPrivateGetAccount: {e}")

print("\nTesting fapiPrivateV2GetAccount...")
try:
    acc = exchange.fapiPrivateV2GetAccount()
    print("Success fapiPrivateV2GetAccount!")
    print(f"Wallet Balance: {acc['totalWalletBalance']}")
except Exception as e:
    print(f"Error fapiPrivateV2GetAccount: {e}")
