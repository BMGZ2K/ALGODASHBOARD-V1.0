import ccxt
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('Binanceapikey').strip() # Strip to remove potential whitespace
SECRET_KEY = os.getenv('BinanceSecretkey').strip()

print(f"Key Length: {len(API_KEY)}")
print(f"Secret Length: {len(SECRET_KEY)}")
print(f"Key First 5: {API_KEY[:5]}")

def test_verbose(name, options):
    print(f"\n--- Testing {name} (Verbose) ---")
    try:
        # Enable verbose to see headers and URLs
        options['verbose'] = True 
        exchange = ccxt.binance(options)
        
        # Force load markets first
        print("Loading markets...")
        exchange.load_markets()
        
        print("Fetching Balance...")
        balance = exchange.fetch_balance()
        print(f"✅ SUCCESS {name}")
    except Exception as e:
        print(f"❌ FAILED {name}")
        # The verbose output will be printed to stdout by ccxt
        
# 3. Test Futures Testnet (Precise Configuration)
print("\n--- Testing Futures Testnet (Precise) ---")
try:
    exchange = ccxt.binance({
        'apiKey': API_KEY,
        'secret': SECRET_KEY,
        'verbose': True,
        'timeout': 30000,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future',
            'adjustForTimeDifference': True
        }
    })

    # Manual Override for Testnet
    exchange.urls['api'] = {
        'fapiPublic': 'https://testnet.binancefuture.com/fapi/v1',
        'fapiPrivate': 'https://testnet.binancefuture.com/fapi/v1',
        'public': 'https://testnet.binancefuture.com/fapi/v1',
        'private': 'https://testnet.binancefuture.com/fapi/v1',
    }
    
    # Force the use of 'future' type for balance
    print("Fetching Futures Balance...")
    # We skip load_markets() if possible, or let it handle itself
    balance = exchange.fetch_balance({'type': 'future'})
    print(f"✅ SUCCESS: Balance found")
    print(f"USDT: {balance['total'].get('USDT', 0)}")

except Exception as e:
    print(f"❌ FAILED: {str(e)}")
