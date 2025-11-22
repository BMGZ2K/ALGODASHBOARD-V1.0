import ccxt
from core.config import API_KEY, SECRET_KEY

exchange = ccxt.binance({
    'apiKey': API_KEY,
    'secret': SECRET_KEY,
    'options': {'defaultType': 'future'}
})

print("Methods with 'Margin' in name:")
for attr in dir(exchange):
    if 'Margin' in attr:
        print(attr)

print("\nMethods with 'allPairs' in name:")
for attr in dir(exchange):
    if 'allPairs' in attr:
        print(attr)
