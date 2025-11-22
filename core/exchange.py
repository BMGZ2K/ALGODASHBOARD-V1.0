import ccxt
import time
from .config import API_KEY, SECRET_KEY, USE_TESTNET, SYMBOLS

def apply_monkey_patches(exchange):
    # FORCE OVERRIDE CAPABILITIES TO PREVENT MARGIN CALLS
    exchange.has['fetchMarginMode'] = False
    exchange.has['fetchMarginModes'] = False 
    exchange.has['setMarginMode'] = False
    
    # MONKEY PATCH to kill load_markets margin check
    def no_op(*args, **kwargs): return {} 
    def no_op_none(*args, **kwargs): return None
    
    exchange.fetch_margin_modes = no_op
    exchange.fetch_margin_mode = no_op_none
    
    # NUCLEAR OPTION: Patch request to intercept the specific URL
    original_request = exchange.request
    def patched_request(path, *args, **kwargs):
        if isinstance(path, str) and ('margin/allPairs' in path or 'margin/isolated/allPairs' in path):
            return [] # Return empty list (expected format for allPairs)
        return original_request(path, *args, **kwargs)
    
    exchange.request = patched_request

    # PATCH SPECIFIC ENDPOINTS THAT CAUSE ERRORS
    # These are the low-level methods CCXT uses
    if hasattr(exchange, 'fapiPrivateGetMarginAllPairs'):
        exchange.fapiPrivateGetMarginAllPairs = no_op
    
    # Just in case it's under a different name or dynamically generated
    exchange.fapiPrivateGetMarginAllPairs = no_op
    
    # Override common problematic methods to avoid SAPI calls
    exchange.has['fetchCurrencies'] = False 
    
    # PATCH: Override fetch_positions to use V2 endpoint which works on Testnet
    def fetch_positions_v2(symbols=None, params={}):
        response = exchange.fapiPrivateV2GetPositionRisk(params)
        return response
    exchange.fetch_positions = fetch_positions_v2 

def get_exchange():
    """
    Initializes the CCXT exchange with necessary configurations and monkey patches
    for Binance Futures Testnet compatibility.
    """
    # Explicitly configure for Binance Futures Testnet based on RAW SUCCESS
    exchange = ccxt.binance({
        'apiKey': API_KEY,
        'secret': SECRET_KEY,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future', 
            'adjustForTimeDifference': True,
            'warnOnFetchOpenOrdersWithoutSymbol': False,
            'fetchBalance': {
                 'type': 'future'
            },
            'defaultMarginMode': 'isolated',
            # 'fetchMarkets': ['future'] # REMOVE THIS LINE, it causes "not supported market type"
        }
    })
    
    apply_monkey_patches(exchange)
    
    if USE_TESTNET:
        print("   ℹ️  Applying Verified Testnet Configuration (demo-fapi)...")
        # 1. Force the URLs that worked in test_demo.py
        exchange.urls['api'] = {
            'fapiPublic': 'https://demo-fapi.binance.com/fapi/v1',
            'fapiPrivate': 'https://demo-fapi.binance.com/fapi/v1',
            'fapiPrivateV2': 'https://demo-fapi.binance.com/fapi/v2',
            'fapiPrivateV3': 'https://demo-fapi.binance.com/fapi/v1', # Map V3 to V1 for Testnet compatibility
            'public': 'https://demo-fapi.binance.com/fapi/v1',
            'private': 'https://demo-fapi.binance.com/fapi/v1',
            'dapiPublic': 'https://demo-fapi.binance.com/fapi/v1',
            'dapiPrivate': 'https://demo-fapi.binance.com/fapi/v1',
        }
        
        # MONKEY PATCH: Completely block fetchOHLCV from checking margins if it does
        exchange.urls['api']['sapi'] = 'https://demo-fapi.binance.com/fapi/v1'
        
        # 3. Define markets manually to avoid load_markets failure (Initial empty state)
        exchange.markets = {}
        exchange.markets_by_id = {}
        
    return exchange

def setup_markets(exchange):
    """
    Loads markets dynamically or falls back to hardcoded precision map if API fails.
    Sets leverage and position mode.
    """
    try:
        # DYNAMIC MARKET LOADING
        print("   🔄 Loading Exchange Markets...")
        try:
            markets = exchange.load_markets()
            print(f"   ✅ Loaded {len(markets)} markets. Sample: {list(markets.keys())[:5]}")
        except Exception as e:
            if "margin" in str(e).lower():
                print("   ⚠️ Margin Check Failed (Expected on Testnet). Ignoring...")
                # If load_markets failed halfway, we might still have data?
                # If not, we must rely on fallback.
            else:
                raise e
        
        # RE-APPLY PATCHES AFTER LOAD (Crucial!)
        apply_monkey_patches(exchange)
        
        # Filter and Map SYMBOLS to Exchange Precision
        for sym in SYMBOLS:
            market = None
            if sym in exchange.markets:
                market = exchange.markets[sym]
            elif f"{sym}:USDT" in exchange.markets:
                market = exchange.markets[f"{sym}:USDT"]
            
            if market:
                m = market
                # Ensure we have the correct precision structure
                prec = m.get('precision', {})
                if 'amount' not in prec: prec['amount'] = 1
                if 'price' not in prec: prec['price'] = 4
                
                # Ensure critical keys exist for CCXT internals
                if 'option' not in m: m['option'] = False
                if 'contract' not in m: m['contract'] = True
                if 'linear' not in m: m['linear'] = True
                
            else:
                # Only remove if we actually successfully loaded markets and this one is missing
                if exchange.markets:
                    print(f"      ⚠️ Symbol {sym} not found in exchange markets! Removing from target list.")
                    if sym in SYMBOLS: SYMBOLS.remove(sym)

    except Exception as e:
        print(f"   ⚠️ Market Load Error: {e}")
        print("   ⚠️ Fallback to Hardcoded Precision (Not Recommended)")
        
        # Fallback (Only if API fails completely)
        precision_map = {
            'BTC/USDT': {'amount': 3, 'price': 1},
            'ETH/USDT': {'amount': 3, 'price': 2},
            'SOL/USDT': {'amount': 0, 'price': 2},
            'BNB/USDT': {'amount': 2, 'price': 2},
            'DOGE/USDT': {'amount': 0, 'price': 5},
            'XRP/USDT': {'amount': 1, 'price': 4},
            'ADA/USDT': {'amount': 0, 'price': 4},
            'AVAX/USDT': {'amount': 0, 'price': 2},
            'DOT/USDT': {'amount': 1, 'price': 3},
            'LINK/USDT': {'amount': 2, 'price': 3},
            'LTC/USDT': {'amount': 3, 'price': 2},
            'TRX/USDT': {'amount': 0, 'price': 5},
            'UNI/USDT': {'amount': 0, 'price': 3},
            'ATOM/USDT': {'amount': 2, 'price': 3},
            'NEAR/USDT': {'amount': 0, 'price': 3},
            'APT/USDT': {'amount': 1, 'price': 2},
            'FIL/USDT': {'amount': 1, 'price': 3},
            'SUI/USDT': {'amount': 1, 'price': 4},
            'ARB/USDT': {'amount': 1, 'price': 4},
            'OP/USDT': {'amount': 1, 'price': 4},
            'TIA/USDT': {'amount': 0, 'price': 4},
            'INJ/USDT': {'amount': 1, 'price': 3},
            'STX/USDT': {'amount': 0, 'price': 4},
            'IMX/USDT': {'amount': 0, 'price': 4},
            'GRT/USDT': {'amount': 0, 'price': 5},
            'SNX/USDT': {'amount': 1, 'price': 3},
            'VET/USDT': {'amount': 0, 'price': 5},
            'THETA/USDT': {'amount': 1, 'price': 3},
            'LDO/USDT': {'amount': 0, 'price': 4},
            'SEI/USDT': {'amount': 0, 'price': 4},
            'ORDI/USDT': {'amount': 1, 'price': 3},
            'FET/USDT': {'amount': 0, 'price': 4},
            'ALGO/USDT': {'amount': 0, 'price': 4},
            'FLOW/USDT': {'amount': 1, 'price': 3},
            'XLM/USDT': {'amount': 0, 'price': 5},
            'CRV/USDT': {'amount': 1, 'price': 4}
        }

        for sym in SYMBOLS:
            market_id = sym.replace('/', '')
            prec = precision_map.get(sym, {'amount': 1, 'price': 4})
            exchange.markets[sym] = {
                'id': market_id,
                'symbol': sym,
                'base': sym.split('/')[0],
                'quote': 'USDT',
                'baseId': sym.split('/')[0],
                'quoteId': 'USDT',
                'active': True,
                'precision': prec,
                'limits': {'amount': {'min': 0.001, 'max': 10000}},
                'type': 'future', 
                'spot': False,
                'future': True,
                'contract': True,
                'option': False, 
                'linear': True
            }
            exchange.markets_by_id[market_id] = exchange.markets[sym]
    
    # Set Leverage and Position Mode
    try:
        for sym in SYMBOLS:
            try:
                # Raw leverage set
                exchange.fapiPrivatePostLeverage({
                    'symbol': sym.replace('/', ''),
                    'leverage': 5
                })
            except Exception as e_lev:
                print(f"      ⚠️ Leverage Error for {sym}: {e_lev}")
                if "-4141" in str(e_lev):
                    print(f"      🚫 Symbol {sym} is CLOSED. Removing...")
                    SYMBOLS.remove(sym)
                    
        print("   ✅ Leverage set to 5x (Raw) for all symbols")
        
        # Ensure Single-Way Mode (Not Hedge Mode)
        try:
            exchange.fapiPrivatePostPositionSideDual({'dualSidePosition': 'false'})
            print("   ✅ Position Mode set to One-Way")
        except Exception as e_dual:
            if "-4059" not in str(e_dual):
                print(f"   ℹ️  Position Mode update: {e_dual}")

    except Exception as e:
        print(f"   ⚠️ Futures Configuration Error: {e}")
