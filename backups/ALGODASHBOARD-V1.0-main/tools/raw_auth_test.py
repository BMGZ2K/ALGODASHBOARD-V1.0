import requests
import time
import hmac
import hashlib
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('Binanceapikey').strip()
SECRET_KEY = os.getenv('BinanceSecretkey').strip()

def test_endpoint(name, base_url):
    print(f"\nTesting {name} [{base_url}]...")
    endpoint = "/api/v3/account"
    timestamp = int(time.time() * 1000)
    query_string = f"timestamp={timestamp}"
    
    signature = hmac.new(
        SECRET_KEY.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    url = f"{base_url}{endpoint}?{query_string}&signature={signature}"
    headers = {
        "X-MBX-APIKEY": API_KEY
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print("✅ SUCCESS! Key is valid for this environment.")
            print(response.json())
            return True
        else:
            print(f"❌ Failed: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return False

print(f"Debugging Key: {API_KEY[:5]}...")

# 1. Spot Testnet
test_endpoint("Spot Testnet", "https://testnet.binance.vision")

# 2. Global Mainnet
test_endpoint("Global Mainnet", "https://api.binance.com")

# 3. US Mainnet
test_endpoint("US Mainnet", "https://api.binance.us")
