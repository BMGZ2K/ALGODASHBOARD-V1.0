import ccxt
import os
from dotenv import load_dotenv
import sys

# Load environment variables (FORCE OVERRIDE)
load_dotenv(override=True)

API_KEY = os.getenv('Binanceapikey', '').strip()
SECRET_KEY = os.getenv('BinanceSecretkey', '').strip()

print("="*60)
print("DIAGNOSTICANDO CONEXÃO COM A BINANCE")
print("="*60)
print(f"Chave API (Início): {API_KEY[:5]}...")
print(f"Chave API (Final):  ...{API_KEY[-5:]}")
print(f"Tamanho da Chave:   {len(API_KEY)} caracteres")
print("-" * 60)

def try_connect(env_name, url_public):
    print(f"\nTentando conectar em: {env_name.upper()}...")
    try:
        exchange = ccxt.binance({
            'apiKey': API_KEY,
            'secret': SECRET_KEY,
            'options': {'defaultType': 'future', 'adjustForTimeDifference': True},
            'enableRateLimit': True
        })
        # Override URLs
        if url_public:
            exchange.urls['api']['fapiPublic'] = url_public
            exchange.urls['api']['fapiPrivate'] = url_public

        # Try to fetch balance
        balance = exchange.fetch_balance()
        print(f"✅ SUCESSO! Conectado ao {env_name}.")
        print(f"   Saldo USDT: {balance['total']['USDT']}")
        return True
    except Exception as e:
        error_msg = str(e)
        if "Invalid Api-Key" in error_msg:
             print(f"❌ FALHA: Chave Inválida para {env_name}.")
        elif "Signature" in error_msg:
             print(f"❌ FALHA: Assinatura Inválida (Secret Key errada?) para {env_name}.")
        else:
             print(f"❌ ERRO: {error_msg}")
        return False

# 1. Testar TESTNET (Ambiente do seu print 'Demo Trad')
connected_testnet = try_connect("FUTURES TESTNET", "https://testnet.binancefuture.com/fapi/v1")

# 3. Testar SPOT TESTNET
print("\nTentando conectar em: SPOT TESTNET...")
try:
    exchange_spot = ccxt.binance({
        'apiKey': API_KEY,
        'secret': SECRET_KEY,
        'options': {'defaultType': 'spot'}
    })
    exchange_spot.urls['api']['public'] = 'https://testnet.binance.vision/api'
    exchange_spot.urls['api']['private'] = 'https://testnet.binance.vision/api'
    balance = exchange_spot.fetch_balance()
    print(f"✅ SUCESSO! Conectado à SPOT TESTNET.")
    print(f"   Saldo: {balance['total']}")
    connected_spot = True
except Exception as e:
    print(f"❌ FALHA SPOT TESTNET: {str(e)}")
    connected_spot = False

print("\n" + "="*60)
print("RESULTADO DO DIAGNÓSTICO")
print("="*60)

if not connected_testnet and not connected_mainnet and not connected_spot:
    print("⚠️  AS CHAVES NÃO FUNCIONAM EM NENHUM AMBIENTE (Futures ou Spot).")
    print("   Possibilidade 1: Você criou as chaves na 'Mock Trading' da Binance.com (essas chaves muitas vezes não funcionam na API externa).")
    print("   Possibilidade 2: Você criou na Testnet correta, mas houve erro na cópia.")
    print("\n   >>> O ROBÔ IRÁ RODAR EM MODO SIMULAÇÃO PARA GARANTIR A OPERAÇÃO. <<<")
elif connected_testnet:
    print("✅  Chaves válidas na FUTURES TESTNET.")
elif connected_spot:
    print("✅  Chaves válidas na SPOT TESTNET.")
