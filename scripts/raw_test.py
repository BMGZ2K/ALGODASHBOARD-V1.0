import time
import hmac
import hashlib
import requests
import os
from urllib.parse import urlencode
from dotenv import load_dotenv

load_dotenv(override=True)

API_KEY = os.getenv('Binanceapikey', '').strip()
SECRET_KEY = os.getenv('BinanceSecretkey', '').strip()

def get_signature(params, secret):
    query_string = urlencode(params)
    return hmac.new(secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()

def test_endpoint(name, base_url):
    print(f"\nTesting {name} [{base_url}]...")
    endpoint = '/fapi/v2/account' # v2 is often more stable for account info
    
    params = {
        'timestamp': int(time.time() * 1000),
        'recvWindow': 5000
    }
    
    params['signature'] = get_signature(params, SECRET_KEY)
    
    headers = {
        'X-MBX-APIKEY': API_KEY
    }
    
    try:
        url = base_url + endpoint
        response = requests.get(url, headers=headers, params=params)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print("✅ SUCCESS!")
            print(f"   Total Wallet Balance: {data.get('totalWalletBalance', 'N/A')}")
            print(f"   Can Trade: {data.get('canTrade', 'N/A')}")
            return True
        else:
            print(f"❌ FAILED: {response.text}")
            return False
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        return False

print("="*60)
print("RAW SIGNATURE TEST (NO LIBRARIES)")
print("="*60)
print(f"Key: {API_KEY[:5]}...{API_KEY[-5:]}")

# 1. Futures Testnet
test_endpoint("FUTURES TESTNET", "https://testnet.binancefuture.com")

# 2. Futures Mainnet (Just in case)
test_endpoint("FUTURES MAINNET", "https://fapi.binance.com")
