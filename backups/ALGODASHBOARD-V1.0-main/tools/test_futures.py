import requests
import time
import hmac
import hashlib
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('Binanceapikey').strip()
SECRET_KEY = os.getenv('BinanceSecretkey').strip()

def test_futures():
    print(f"Testing Futures API (fapi.binance.com)...")
    base_url = "https://fapi.binance.com"
    endpoint = "/fapi/v2/account" # Futures account info
    timestamp = int(time.time() * 1000)
    query_string = f"timestamp={timestamp}"
    
    signature = hmac.new(
        SECRET_KEY.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    url = f"{base_url}{endpoint}?{query_string}&signature={signature}"
    headers = {"X-MBX-APIKEY": API_KEY}
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print("✅ SUCCESS! This is a FUTURES key.")
            print(response.json())
        else:
            print(f"❌ Failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

# Also Test Futures Testnet
def test_futures_testnet():
    print(f"\nTesting Futures TESTNET (testnet.binancefuture.com)...")
    base_url = "https://testnet.binancefuture.com"
    endpoint = "/fapi/v2/account"
    timestamp = int(time.time() * 1000)
    query_string = f"timestamp={timestamp}"
    
    signature = hmac.new(
        SECRET_KEY.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    url = f"{base_url}{endpoint}?{query_string}&signature={signature}"
    headers = {"X-MBX-APIKEY": API_KEY}
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print("✅ SUCCESS! This is a FUTURES TESTNET key.")
        else:
            print(f"❌ Failed: {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_futures()
    test_futures_testnet()
