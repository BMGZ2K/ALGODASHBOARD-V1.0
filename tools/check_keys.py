import ccxt
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('Binanceapikey')
SECRET_KEY = os.getenv('BinanceSecretkey')

def test_connection(name, options, is_testnet=False):
    print(f"\nTesting {name}...")
    try:
        exchange = ccxt.binance(options)
        if is_testnet:
            # DO NOT use set_sandbox_mode(True) to avoid deprecation error
            # exchange.set_sandbox_mode(True) 
            
            # Manual override for Futures Testnet
            exchange.urls['api']['fapiPublic'] = 'https://testnet.binancefuture.com/fapi/v1'
            exchange.urls['api']['fapiPrivate'] = 'https://testnet.binancefuture.com/fapi/v1'
            print("   (URLs manually rewritten to Testnet)")
            
        exchange.load_markets()
        balance = exchange.fetch_balance()
        print(f"✅ SUCCESS connecting to {name}")
        print(f"   USDT Balance: {balance['total'].get('USDT', 0)}")
        return True
    except Exception as e:
        print(f"❌ FAILED {name}: {str(e)[:200]}...")
        return False

# 1. Test Futures TESTNET
options_testnet = {
    'apiKey': API_KEY,
    'secret': SECRET_KEY,
    'options': {'defaultType': 'future'}
}
test_connection("Futures TESTNET", options_testnet, is_testnet=True)

# 3. Test SPOT TESTNET
options_spot_testnet = {
    'apiKey': API_KEY,
    'secret': SECRET_KEY,
    'options': {'defaultType': 'spot'}
}
print(f"\nTesting SPOT TESTNET...")
try:
    exchange = ccxt.binance(options_spot_testnet)
    # Manual override for Spot Testnet
    exchange.urls['api']['public'] = 'https://testnet.binance.vision/api'
    exchange.urls['api']['private'] = 'https://testnet.binance.vision/api'
    
    exchange.load_markets()
    balance = exchange.fetch_balance()
    print(f"✅ SUCCESS connecting to SPOT TESTNET")
    print(f"   Balances: {balance['total']}")
except Exception as e:
    print(f"❌ FAILED SPOT TESTNET: {str(e)[:200]}...")
