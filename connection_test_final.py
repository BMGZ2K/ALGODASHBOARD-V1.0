import ccxt
import os
from dotenv import load_dotenv

load_dotenv(override=True)

API_KEY = os.getenv('Binanceapikey', '').strip()
SECRET_KEY = os.getenv('BinanceSecretkey', '').strip()

print("="*60)
print("TESTE FINAL DE CONEXÃO - DEEP DEBUG")
print("="*60)

# 1. TESTAR SPOT TESTNET (Novo Endpoint)
# Documentação recente aponta: https://testnet.binance.vision/api
print("\n1. TESTANDO SPOT TESTNET (testnet.binance.vision)...")
try:
    exchange_spot = ccxt.binance({
        'apiKey': API_KEY,
        'secret': SECRET_KEY,
        'options': {'defaultType': 'spot'}
    })
    exchange_spot.urls['api']['public'] = 'https://testnet.binance.vision/api'
    exchange_spot.urls['api']['private'] = 'https://testnet.binance.vision/api'
    
    balance = exchange_spot.fetch_balance()
    print("✅ SUCESSO SPOT! As chaves são para Spot Testnet.")
    print(f"   Saldo: {balance['total']}")
except Exception as e:
    print(f"❌ FALHA SPOT: {e}")

# 2. TESTAR FUTURES TESTNET (Oficial)
# Endpoint oficial: https://testnet.binancefuture.com/fapi/v1
print("\n2. TESTANDO FUTURES TESTNET (testnet.binancefuture.com)...")
try:
    exchange_fut = ccxt.binance({
        'apiKey': API_KEY,
        'secret': SECRET_KEY,
        'options': {'defaultType': 'future'}
    })
    # Manual override agressivo para garantir
    exchange_fut.urls['api']['fapiPublic'] = 'https://testnet.binancefuture.com/fapi/v1'
    exchange_fut.urls['api']['fapiPrivate'] = 'https://testnet.binancefuture.com/fapi/v1'
    
    balance = exchange_fut.fetch_balance()
    print("✅ SUCESSO FUTURES! As chaves são para Futures Testnet.")
    print(f"   Saldo USDT: {balance['total']['USDT']}")
except Exception as e:
    print(f"❌ FALHA FUTURES: {e}")

# 3. TESTAR DEMO TRADING (Endpoint Alternativo Mock)
# Algumas contas novas são 'Mock' e não 'Testnet'
# Endpoint: https://demo-api.binance.com (Sugerido em issues recentes)
print("\n3. TESTANDO DEMO API (demo-api.binance.com) [Experimental]...")
try:
    exchange_demo = ccxt.binance({
        'apiKey': API_KEY,
        'secret': SECRET_KEY,
        'options': {'defaultType': 'spot'} # Geralmente mock é spot first
    })
    exchange_demo.urls['api']['public'] = 'https://demo-api.binance.com/api'
    exchange_demo.urls['api']['private'] = 'https://demo-api.binance.com/api'
    
    balance = exchange_demo.fetch_balance()
    print("✅ SUCESSO DEMO API! As chaves são para o novo Mock Environment.")
    print(f"   Saldo: {balance['total']}")
except Exception as e:
    print(f"❌ FALHA DEMO API: {e}")
