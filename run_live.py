import ccxt
import pandas as pd
import pandas_ta as ta
import time
import os
import json
import ast
import argparse
import csv
from datetime import datetime
from dotenv import load_dotenv
import traceback

# Load Environment Variables
load_dotenv(override=True)

# Configuração
USE_TESTNET = os.getenv('TESTNET', 'True').lower() == 'true'
API_KEY = os.getenv('Binanceapikey', '').strip()
SECRET_KEY = os.getenv('BinanceSecretkey', '').strip()
LOG_FILE = "trades_log.csv"
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'DOGE/USDT']

def log_trade(timestamp, symbol, side, amount, price, reason, status):
    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, mode='a', newline='') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(['timestamp', 'symbol', 'side', 'amount', 'price', 'reason', 'status'])
        writer.writerow([timestamp, symbol, side, amount, price, reason, status])

def get_exchange():
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
    
    # FORCE OVERRIDE CAPABILITIES TO PREVENT MARGIN CALLS
    exchange.has['fetchMarginMode'] = False
    exchange.has['setMarginMode'] = False
    
    # MONKEY PATCH to kill load_markets margin check
    def no_op(*args, **kwargs): return None
    exchange.fetch_margin_modes = no_op
    
    # 2nd MONKEY PATCH: Explicitly overwrite the internal method that calls 'margin/allPairs'
    # In some CCXT versions, this might be fetchMarginModes or similar
    # We blindly patch typical suspects
    exchange.fetch_margin_mode = no_op
    
    if USE_TESTNET:
        print("   ℹ️  Applying Verified Testnet Configuration (demo-fapi)...")
        # 1. Force the URLs that worked in test_demo.py
        exchange.urls['api'] = {
            'fapiPublic': 'https://demo-fapi.binance.com/fapi/v1',
            'fapiPrivate': 'https://demo-fapi.binance.com/fapi/v1',
            'fapiPrivateV2': 'https://demo-fapi.binance.com/fapi/v2', # Added V2 for Account
            'public': 'https://demo-fapi.binance.com/fapi/v1',
            'private': 'https://demo-fapi.binance.com/fapi/v1',
        }
        
        # Override common problematic methods to avoid SAPI calls
        # CCXT often tries to fetch generic account info via SAPI
        exchange.has['fetchCurrencies'] = False 
        
        # MONKEY PATCH: Completely block fetchOHLCV from checking margins if it does
        # And ensure any internal SAPI call is rerouted or blocked
        exchange.urls['api']['sapi'] = 'https://demo-fapi.binance.com/fapi/v1'
        
        # 3. Define markets manually to avoid load_markets failure
        exchange.markets = {}
        exchange.markets_by_id = {}
        
        # Precision Mapping (approximate for Testnet)
        # Most altcoins allow 0 or 1 decimal for amount
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

        # Manual Market Definition (Crucial for Testnet & CCXT Validation)
        # We must provide 'type', 'future', etc. to prevent CCXT from crashing on validation
        for symbol in SYMBOLS:
            market_id = symbol.replace('/', '')
            # Default to 1 decimal amount if not found
            prec = precision_map.get(symbol, {'amount': 1, 'price': 4})
            
            exchange.markets[symbol] = {
                'id': market_id,
                'symbol': symbol,
                'base': symbol.split('/')[0],
                'quote': 'USDT',
                'type': 'future',
                'spot': False,
                'future': True,
                'linear': True,
                'contract': True,
                'active': True,
                'precision': {
                    'amount': prec['amount'],
                    'price': prec['price'] 
                },
                'limits': {
                    'amount': {
                        'min': 0.001,
                        'max': 1000000
                    },
                    'price': {
                        'min': 0.01,
                        'max': 1000000
                    },
                    'cost': {
                        'min': 5.0,
                        'max': 1000000
                    }
                },
                'info': {
                    # Mocking Binance Info to satisfy CCXT validation
                    'orderTypes': [
                        'LIMIT', 'MARKET', 'STOP', 'STOP_MARKET', 
                        'TAKE_PROFIT', 'TAKE_PROFIT_MARKET', 'TRAILING_STOP_MARKET'
                    ]
                } 
            }
            exchange.markets_by_id[market_id] = exchange.markets[symbol]
            
        # 2. CRITICAL: Disable sandbox mode flag which breaks CCXT 4.x+
        # exchange.set_sandbox_mode(True)  <-- DO NOT USE
        
        # 3. Adjust other internal flags if needed
        # Some CCXT versions default to /fapi/v1, ensuring it stays there
    
    return exchange

def load_strategy_config(strategy_name):
    path = f"best_strategies/{strategy_name}_config.txt"
    if not os.path.exists(path):
        return {'st_len': 10, 'st_mult': 3.0, 'rsi_len': 14, 'rsi_buy': 40, 'breakout_window': 96}
    with open(path, 'r') as f:
        return ast.literal_eval(f.read())

def analyze_symbol(symbol, exchange, pos_data, usdt_balance, available_balance, is_spot, is_sim, global_sentiment):
    try:
        # Fetch Data
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=100)
        if not ohlcv: return None
        
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        current_price = df.iloc[-1]['close']
        
        # --- SMART CONFIG (Hardcoded for Auto-Pilot) ---
        USE_HEIKIN_ASHI = True
        RISK_PER_TRADE = 0.02 # 2% Risk
        LEVERAGE_CAP = 5 # 5x Max Leverage
        
        # --- DATA PREPARATION ---
        # Heikin Ashi Smoothing
        if USE_HEIKIN_ASHI:
            df['ha_close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
            # Initialize ha_open with open
            df['ha_open'] = df['open']
            # Vectorized approximation for speed:
            df['ha_open'] = (df['open'].shift(1) + df['close'].shift(1)) / 2
            df.loc[df.index[0], 'ha_open'] = df['open'].iloc[0] # Fix first NaN using .loc
            
            df['ha_high'] = df[['high', 'open', 'close']].max(axis=1)
            df['ha_low'] = df[['low', 'open', 'close']].min(axis=1)
            
            # Use HA values for indicators
            calc_high, calc_low, calc_close = df['ha_high'], df['ha_low'], df['ha_close']
        else:
            calc_high, calc_low, calc_close = df['high'], df['low'], df['close']

        # --- INDICATORS (Using Smoothed or Raw) ---
        # ATR (Always use raw for true volatility)
        atr = ta.atr(df['high'], df['low'], df['close'], length=14)
        current_atr = atr.iloc[-1]
        
        # RSI
        rsi = ta.rsi(calc_close, length=14)
        rsi_value = rsi.iloc[-1]
        
        # ADX
        adx = ta.adx(calc_high, calc_low, calc_close, length=14)
        adx_col = [c for c in adx.columns if c.startswith('ADX')][0]
        current_adx = adx.iloc[-1][adx_col]
        
        # SuperTrend (Fast)
        st = ta.supertrend(calc_high, calc_low, calc_close, length=10, multiplier=1.5)
        st_dir_col = [c for c in st.columns if c.startswith('SUPERTd')][0]
        current_trend = st.iloc[-1][st_dir_col]
        
        # SuperTrend (Slow)
        st_slow = ta.supertrend(calc_high, calc_low, calc_close, length=60, multiplier=3.0)
        st_slow_dir_col = [c for c in st_slow.columns if c.startswith('SUPERTd')][0]
        slow_trend = st_slow.iloc[-1][st_slow_dir_col]

        # Bollinger Bands & Squeeze
        bb = ta.bbands(calc_close, length=20, std=2.0)
        lower_col = [c for c in bb.columns if c.startswith('BBL')][0]
        upper_col = [c for c in bb.columns if c.startswith('BBU')][0]
        lower_bb = bb.iloc[-1][lower_col]
        upper_bb = bb.iloc[-1][upper_col]
        
        # Squeeze Metrics
        df['bb_width'] = (bb[upper_col] - bb[lower_col]) / calc_close
        df['bb_w_sma'] = ta.sma(df['bb_width'], length=20)
        current_width = df.iloc[-1]['bb_width']
        width_threshold = df.iloc[-1]['bb_w_sma']
        
        # Volume SMA
        df['vol_sma'] = ta.sma(df['volume'], length=20)
        current_vol = df.iloc[-1]['volume']
        vol_sma = df.iloc[-1]['vol_sma']
        
        # Stochastic RSI
        rsi_series = rsi
        min_rsi = rsi_series.rolling(14).min()
        max_rsi = rsi_series.rolling(14).max()
        stoch = (rsi_series - min_rsi) / (max_rsi - min_rsi)
        df['stoch_k'] = stoch.rolling(3).mean() * 100
        df['stoch_d'] = df['stoch_k'].rolling(3).mean()
        stoch_k = df.iloc[-1]['stoch_k']
        stoch_d = df.iloc[-1]['stoch_d']
        prev_stoch_k = df.iloc[-2]['stoch_k']
        prev_stoch_d = df.iloc[-2]['stoch_d']

        # Strategy Logic
        signal_msg = "WAIT"
        action = None
        current_pos = pos_data['amt']
        
        # EXIT LOGIC
        if current_pos != 0:
            atr_stop_mult = 2.0
            entry = pos_data['entry']
            pnl_per_unit = (current_price - entry) if current_pos > 0 else (entry - current_price)
            
            # 1. Hard Take Profit (4x ATR) - Bank Big Wins
            if pnl_per_unit > (current_atr * 4.0):
                signal_msg = "EXIT_TP"
                side = 'sell' if current_pos > 0 else 'buy'
                action = {'symbol': symbol, 'side': side, 'amount': abs(current_pos), 'price': current_price, 'reason': signal_msg, 'reduceOnly': True}
            
            # 2. Dynamic Trailing Stop (Aggressive)
            else:
                # EVOLUTION: Tighten sooner to reduce give-back
                if pnl_per_unit > (current_atr * 1.0): # Was 1.5
                    atr_stop_mult = 0.5 # Very tight trail to lock profit
                elif pnl_per_unit > (current_atr * 0.5):
                    atr_stop_mult = 1.0 # Breakeven-ish
                    
                if current_pos > 0: # LONG
                    stop_price = entry - (current_atr * atr_stop_mult)
                    trail_stop = current_price - (current_atr * atr_stop_mult)
                    effective_stop = max(stop_price, trail_stop)
                    
                    if current_price < effective_stop:
                        signal_msg = "EXIT_STOP"
                        action = {'symbol': symbol, 'side': 'sell', 'amount': abs(current_pos), 'price': current_price, 'reason': signal_msg, 'reduceOnly': True}
                        
                elif current_pos < 0: # SHORT
                    stop_price = entry + (current_atr * atr_stop_mult)
                    trail_stop = current_price + (current_atr * atr_stop_mult)
                    effective_stop = min(stop_price, trail_stop)
                    
                    if current_price > effective_stop:
                        signal_msg = "EXIT_STOP"
                        action = {'symbol': symbol, 'side': 'buy', 'amount': abs(current_pos), 'price': current_price, 'reason': signal_msg, 'reduceOnly': True}
                    
        # ENTRY LOGIC
        else:
            target_dir = 0
            
            # Adaptive Thresholds based on Global Sentiment
            rsi_long_threshold = 50
            rsi_short_threshold = 50
            
            if global_sentiment > 0.6: 
                rsi_long_threshold = 55 
            elif global_sentiment < 0.4: 
                rsi_short_threshold = 45 

            # Regime Detection
            if current_adx > 25: # Trend
                # Volume Filter
                if current_vol > vol_sma:
                    # STANDARD PULLBACK ENTRY (Must align with Slow Trend)
                    if current_trend == slow_trend:
                        if current_trend == 1 and rsi_value < rsi_long_threshold:
                            target_dir = 1
                            signal_msg = "LONG_TREND_ALIGNED"
                        elif current_trend == -1 and rsi_value > rsi_short_threshold:
                            target_dir = -1
                            signal_msg = "SHORT_TREND_ALIGNED"
                    
                    # MOMENTUM BREAKOUT (High ADX)
                    if current_adx > 40:
                        if current_trend == 1 and rsi_value < 70:
                            target_dir = 1
                            signal_msg = "LONG_MOMENTUM_BREAKOUT"
                        elif current_trend == -1 and rsi_value > 30:
                            target_dir = -1
                            signal_msg = "SHORT_MOMENTUM_BREAKOUT"

            else: # Range / Squeeze
                # 1. VOLATILITY SQUEEZE BREAKOUT (High Profit)
                if current_width < width_threshold: 
                    if current_price > upper_bb and current_vol > vol_sma:
                        target_dir = 1
                        signal_msg = "LONG_SQUEEZE_BREAKOUT"
                    elif current_price < lower_bb and current_vol > vol_sma:
                        target_dir = -1
                        signal_msg = "SHORT_SQUEEZE_BREAKOUT"
                
                # 2. STOCHASTIC SCALPING (High Frequency)
                # Only if not in squeeze (to avoid fakeouts)
                else:
                    # Long Scalp: Oversold + Crossover Up
                    if stoch_k < 20 and stoch_k > stoch_d and prev_stoch_k < prev_stoch_d:
                        target_dir = 1
                        signal_msg = "LONG_SCALP_STOCH"
                    
                    # Short Scalp: Overbought + Crossover Down
                    elif stoch_k > 80 and stoch_k < stoch_d and prev_stoch_k > prev_stoch_d:
                        target_dir = -1
                        signal_msg = "SHORT_SCALP_STOCH"
                    
                    # 3. Mean Reversion (Backup)
                    elif current_price < lower_bb:
                        target_dir = 1
                        signal_msg = "LONG_RANGE_BB"
                    elif current_price > upper_bb:
                        target_dir = -1
                        signal_msg = "SHORT_RANGE_BB"
            
            # DYNAMIC POSITION SIZING (Smart Margin)
            if target_dir != 0:
                # Risk Amount
                risk_amt = usdt_balance * RISK_PER_TRADE
                
                # Stop Distance (2 ATR)
                stop_dist = current_atr * 2.0
                if stop_dist == 0: stop_dist = current_price * 0.01 # Fallback
                
                # Quantity based on Risk
                qty_risk = risk_amt / stop_dist
                
                # Quantity based on Leverage Cap
                max_qty_lev = (usdt_balance * LEVERAGE_CAP) / current_price
                
                # Quantity based on Available Margin (Critical for "Insufficient Margin" fix)
                # Leave 5% buffer
                max_qty_margin = (available_balance * 0.95 * LEVERAGE_CAP) / current_price
                
                # Final Quantity (Min of all constraints)
                final_qty = min(qty_risk, max_qty_lev, max_qty_margin)
                
                # Ensure minimum notional (approx $6 for Binance)
                if (final_qty * current_price) < 6:
                    final_qty = 0 # Skip if too small
                
                if final_qty > 0:
                    side = 'buy' if target_dir == 1 else 'sell'
                    action = {'symbol': symbol, 'side': side, 'amount': final_qty, 'price': current_price, 'reason': signal_msg}

        return {
            'symbol': symbol,
            'price': current_price,
            'trend': current_trend,
            'rsi': rsi_value,
            'adx': current_adx,
            'signal': signal_msg,
            'position': current_pos,
            'pnl': pos_data['pnl'],
            'action': action
        }

    except Exception as e:
        print(f"Error analyzing {symbol}: {e}")
        return None

# Global Configuration
# Global Configuration
# Top 35 Liquid Futures Pairs (Cleaned)
SYMBOLS = [
    'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'DOGE/USDT',
    'XRP/USDT', 'ADA/USDT', 'AVAX/USDT', 'DOT/USDT', 'LINK/USDT',
    'LTC/USDT', 'TRX/USDT', 'UNI/USDT', 'ATOM/USDT', 'NEAR/USDT',
    'APT/USDT', 'FIL/USDT', 'SUI/USDT', 'ARB/USDT', 'OP/USDT',
    'INJ/USDT', 'STX/USDT', 'IMX/USDT', 'GRT/USDT',
    'SNX/USDT', 'VET/USDT', 'THETA/USDT', 'LDO/USDT', 'TIA/USDT',
    'SEI/USDT', 'ORDI/USDT', 'FET/USDT',
    'ALGO/USDT', 'FLOW/USDT', 'XLM/USDT', 'CRV/USDT'
]

def execute_trade_safely(exchange, symbol, side, amount, price, params, current_margin, active_positions, blacklist, signal_msg):
    """
    Executes a trade with robust error handling, retries, and raw API calls.
    Updates active_positions and returns the updated current_margin.
    """
    attempts = 0
    executed = False
    final_amount = amount
    leverage = 2 # Hardcoded
    
    while attempts < 3 and not executed:
        try:
            # Dynamic precision formatting
            prec_amount = exchange.markets[symbol]['precision']['amount']
            fmt_str = "{:." + str(prec_amount) + "f}"
            qty_str = fmt_str.format(final_amount)

            # BYPASS CCXT VALIDATION: Use raw API call
            req_params = {
                'symbol': symbol.replace('/', ''),
                'side': side.upper(),
                'type': 'MARKET',
                'quantity': qty_str,
            }
            
            if params.get('reduceOnly', False):
                req_params['reduceOnly'] = 'true'
            
            # Execute Raw Order
            order = exchange.fapiPrivatePostOrder(req_params)
            
            executed = True
            log_trade(datetime.now().isoformat(), symbol, side, final_amount, price, signal_msg, "FILLED")
            print(f"      ✅ FILLED: {order['orderId']}")
            
            # Update active_positions immediately
            if side == 'buy':
                active_positions[symbol] = {'amt': final_amount, 'entry': price, 'pnl': 0.0}
            else: # sell
                if symbol in active_positions:
                    del active_positions[symbol] # Assuming full close
                else: # Opening short
                    active_positions[symbol] = {'amt': -final_amount, 'entry': price, 'pnl': 0.0}
            
            # Update Local Margin (only if opening/increasing risk)
            # Simple logic: if we spent margin, deduct it.
            # If reduceOnly, we theoretically gain margin, but let's be conservative and only deduct for new risk.
            if not params.get('reduceOnly', False):
                used_margin = (final_amount * price) / leverage
                current_margin -= used_margin
                print(f"      ℹ️  Margin Updated: ${current_margin:.2f} remaining")

        except Exception as order_e:
            err_msg = str(order_e).lower()
            # print(f"DEBUG: Traceback: {traceback.format_exc()}") 
            
            if "margin" in err_msg or "balance" in err_msg or "account has insufficient balance" in err_msg:
                print(f"      ⚠️ Insufficient Margin. Retrying with 50% size...")
                final_amount *= 0.5
                attempts += 1
                time.sleep(0.5)
                
                # Check min amount
                min_amt = 0.001
                try:
                    min_amt = exchange.markets[symbol]['limits']['amount']['min']
                except:
                    pass
                    
                if final_amount < min_amt:
                    print(f"      ❌ Reduced amount {final_amount:.4f} is below minimum. Aborting.")
                    break
            elif "argument of type 'nonetype' is not iterable" in err_msg:
                # This shouldn't happen with raw call, but keep for safety
                print(f"      ⚠️ CCXT NoneType Error. Retrying...")
                attempts += 1
                time.sleep(0.5)
            else:
                # Other errors (e.g. network)
                print(f"      ❌ Order Error: {err_msg}")
                attempts += 1
                time.sleep(0.5)
    
    if not executed:
        print(f"   ❌ Order Failed for {symbol} after retries.")
        log_trade(datetime.now().isoformat(), symbol, side, amount, price, signal_msg, f"FAILED: No execution after retries")
        
        # Self-Healing for persistent failures
        # We can't easily check the exact error here as it was caught in the loop
        # But if it failed 3 times, maybe blacklist it temporarily?
        # For now, keep simple.

    return current_margin

def run_bot(snapshot=False):
    # --- MULTI-SYMBOL CONFIGURATION ---
    MAX_POSITIONS = 20 # Increased exposure for 36 pairs
    BLACKLIST = set() # Self-healing mechanism for problematic symbols
    
    print(f"🚀 LIVE BOT INITIALIZED | Mode: {'TESTNET' if USE_TESTNET else 'LIVE'}")
    print(f"Targets: {len(SYMBOLS)} Pairs | Strategy: Multi-Regime Hybrid + MTF Alignment + Stoch Scalp")
    
    # Load default config (can be per-symbol later)
    config = {'st_len': 10, 'st_mult': 3.0, 'rsi_len': 14, 'rsi_buy': 40, 'breakout_window': 96}
    
    exchange = get_exchange()
    
    # INITIAL DASHBOARD EXPORT (Empty State)
    # Ensures dashboard has something to read immediately
    try:
        initial_state = {
            'timestamp': datetime.now().isoformat(),
            'balance': 0.0,
            'positions': {},
            'market_scan': {}
        }
        with open('dashboard_state.json', 'w') as f:
            json.dump(initial_state, f)
    except Exception as e:
        print(f"Initial State Error: {e}")
    
    SIMULATION_MODE = False
    
    # --- FUTURES CONFIGURATION ---
    IS_SPOT_MODE = False
    
    if not snapshot:
        try:
            # Manually skip fetchMarginMode by ensuring exchange thinks it's unsupported
            # The set_margin_mode call below is what triggers it usually
            
            # ULTIMATE FIX: Initialize markets manually if load_markets fails on margin check
            try:
                exchange.load_markets()
            except Exception as load_err:
                if "margin/allPairs" in str(load_err):
                     print("   ⚠️ Skipping Margin Check (Not supported on Testnet)")
                     # CCXT usually loads markets before failing on margin. 
                     # If it failed partway, we might still have markets.
                     if not exchange.markets:
                         print("   ❌ Markets not loaded. Attempting minimal reload...")
                         # This is risky but we have no choice if API is broken
                else:
                     raise load_err

            # Precision Mapping (approximate for Testnet)
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
                'TIA/USDT': {'amount': 0, 'price': 4}, # Fixed TIA precision
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

            try:
                for sym in SYMBOLS:
                    market_id = sym.replace('/', '')
                    # Default to 1 decimal amount if not found
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
                        'linear': True,  
                        'info': {}
                    }
                    exchange.markets_by_id[market_id] = exchange.markets[sym]
                
                for sym in SYMBOLS:
                    # exchange.set_leverage(2, sym) # This also triggers margin checks sometimes
                    # Raw leverage set
                    exchange.fapiPrivatePostLeverage({
                        'symbol': sym.replace('/', ''),
                        'leverage': 2
                    })
                print("   ✅ Leverage set to 2x (Raw) for all symbols")
                
                # Ensure Single-Way Mode (Not Hedge Mode) which causes -4061
                # Check position mode first? No, just force it.
                try:
                    exchange.fapiPrivatePostPositionSideDual({'dualSidePosition': 'false'})
                    print("   ✅ Position Mode set to One-Way")
                except Exception as e_dual:
                    # -4059: No need to change position side.
                    if "-4059" not in str(e_dual):
                        print(f"   ℹ️  Position Mode update: {e_dual}")

            except Exception as e:
                print(f"   ⚠️ Futures Configuration Error: {e}")
            
            # try:
            #     exchange.set_margin_mode('ISOLATED', symbol)
            # except:
            #     pass
        except Exception as e:
            print(f"❌ FATAL: Error connecting to Futures: {e}")
            if not USE_TESTNET: 
                return 

    # Simulation State (Keeping simulation vars just in case, but Logic will prefer Real Execution)
    sim_balance = 1000.0
    # sim_pos_amt and sim_entry_price would need to be per-symbol for multi-symbol simulation
    
    # Polling Interval
    POLL_INTERVAL = 10 # Scan every 10s
    
    # --- SESSION PERSISTENCE ---
    SESSION_FILE = "session_info.json"
    initial_balance = 0.0
    
    # Fetch initial balance for session tracking
    try:
        account = exchange.fapiPrivateV2GetAccount()
        current_bal = float(account['totalWalletBalance'])
        
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE, 'r') as f:
                session_data = json.load(f)
            initial_balance = session_data.get('initial_balance', current_bal)
            print(f"   🔄 Session Resumed. Start Balance: ${initial_balance:.2f}")
        else:
            initial_balance = current_bal
            with open(SESSION_FILE, 'w') as f:
                json.dump({'initial_balance': initial_balance, 'start_time': datetime.now().isoformat()}, f)
            print(f"   🆕 New Session Started. Start Balance: ${initial_balance:.2f}")
            
    except Exception as e:
        print(f"   ⚠️ Session Init Error: {e}")
        initial_balance = 0.0 # Fallback

    # State Tracking for Dashboard
    system_state = {sym: {'price': 0.0, 'trend': 0, 'rsi': 0, 'adx': 0, 'signal': 'IDLE', 'pos': 0.0, 'pnl': 0.0} for sym in SYMBOLS}
    
    # --- MAIN LOOP ---
    global_sentiment = 0.5 # Neutral start
    COMMAND_FILE = "bot_commands.json"
    
    # SMART AUTO-PILOT CONFIG
    # No external config file, just pure logic
    MAX_POSITIONS = 20
    
    while True:
        try:
            # --- COMMAND HANDLING ---
            if os.path.exists(COMMAND_FILE):
                try:
                    with open(COMMAND_FILE, 'r') as f:
                        cmd_data = json.load(f)
                    
                    if cmd_data.get('command') == 'CLOSE_ALL':
                        print("🚨 RECEIVED PANIC COMMAND: CLOSING ALL POSITIONS")
                        
                        # Refresh positions first to be sure
                        positions = exchange.fetch_positions()
                        for p in positions:
                            amt = float(p['contracts']) if 'contracts' in p else float(p['positionAmt'])
                            if amt != 0:
                                sym = p['symbol']
                                side = 'sell' if amt > 0 else 'buy'
                                print(f"   🔥 PANIC CLOSE: {sym} {amt}")
                                try:
                                    exchange.create_market_order(sym, side, abs(amt), params={'reduceOnly': True})
                                except Exception as e:
                                    print(f"   ❌ Panic Close Failed for {sym}: {e}")
                        
                        # Clear file
                        os.remove(COMMAND_FILE)
                        print("   ✅ All positions closed (attempted).")
                        time.sleep(5) # Wait for dust to settle
                        continue # Skip scan this loop
                        
                except Exception as e:
                    print(f"Command Error: {e}")

            # Filter Blacklisted Symbols
            ACTIVE_SYMBOLS = [s for s in SYMBOLS if s not in BLACKLIST]
            
            print(f"\n--- 🔎 Scanning Market ({len(ACTIVE_SYMBOLS)} Pairs) | Sentiment: {global_sentiment:.2f} ---")
            # 1. Fetch Account Balance & Positions (Global)
            usdt_balance = 0.0
            available_balance = 0.0
            realized_pnl = 0.0
            active_positions = {} 
            
            if not SIMULATION_MODE:
                try:
                    # Optimized: Fetch Account & Positions in ONE call
                    # This avoids the /margin/isolated error and is faster
                    account_info = exchange.fapiPrivateV2GetAccount()
                    
                    # Balance
                    usdt_balance = float(account_info['totalWalletBalance'])
                    available_balance = float(account_info['availableBalance'])
                    
                    # Realized PnL (Session)
                    if initial_balance > 0:
                        realized_pnl = usdt_balance - initial_balance
                    
                    # Positions
                    for p in account_info['positions']:
                        amt = float(p['positionAmt'])
                        if amt != 0:
                            sym = p['symbol']
                            # Convert 'ETHUSDT' -> 'ETH/USDT'
                            # We need to match the symbol format in SYMBOLS
                            # Efficient matching:
                            matched_sym = next((s for s in ACTIVE_SYMBOLS if s.replace('/', '') == sym), None)
                            
                            if matched_sym:
                                entry = float(p['entryPrice'])
                                pnl = float(p['unrealizedProfit'])
                                active_positions[matched_sym] = {'amt': amt, 'entry': entry, 'pnl': pnl}
                                
                except Exception as e:
                    print(f"⚠️ Account Sync Error: {e}")
                    usdt_balance = 0.0 
            else:
                # SIMULATION MODE (Placeholder)
                usdt_balance = 10000.0 # Default sim balance
                available_balance = 10000.0
            
            print(f"\n--- 🔎 Scan ({len(ACTIVE_SYMBOLS)} Pairs) | Sent: {global_sentiment:.2f} | PnL: ${realized_pnl:.2f} | Margin: ${available_balance:.2f} ---")
            
            # 2. Scan & Execute for Each Symbol
            proposed_actions = []
            current_market_scan_data = {}
            current_trends = [] # For sentiment calculation

            for symbol in ACTIVE_SYMBOLS:
                current_pos_data = active_positions.get(symbol, {'amt': 0.0, 'entry': 0.0, 'pnl': 0.0})
                analysis_result = analyze_symbol(symbol, exchange, current_pos_data, usdt_balance, available_balance, IS_SPOT_MODE, SIMULATION_MODE, global_sentiment)
                
                if analysis_result:
                    current_market_scan_data[symbol] = {
                        'price': analysis_result['price'],
                        'trend': 'BULL' if analysis_result['trend'] == 1 else ('BEAR' if analysis_result['trend'] == -1 else 'SIDEWAYS'),
                        'rsi': analysis_result['rsi'],
                        'adx': analysis_result['adx'],
                        'signal': analysis_result['signal'],
                        'pos': analysis_result['position'],
                        'pnl': analysis_result['pnl']
                    }
                    
                    # Collect Trend for Sentiment
                    current_trends.append(analysis_result['trend'])

                    if analysis_result['action']:
                        proposed_actions.append(analysis_result['action'])
            
            # Calculate Global Sentiment for NEXT loop
            if current_trends:
                bull_count = current_trends.count(1)
                global_sentiment = bull_count / len(current_trends)

            # 3. Prioritize and Execute Actions (Simple FIFO for now, could add scoring)
            # Track margin locally to prevent multiple orders from exhausting balance simultaneously
            current_available_margin = available_balance
            leverage = 2 # Hardcoded as per init

            for action in proposed_actions:
                symbol = action['symbol']
                side = action['side']
                abs_delta = action['amount']
                current_price = action['price']
                signal_msg = action['reason']

                # Check if we are already at MAX_POSITIONS and this is an entry signal
                is_entry = (side == 'buy' and current_market_scan_data[symbol]['pos'] <= 0) or \
                           (side == 'sell' and current_market_scan_data[symbol]['pos'] >= 0)
                
                if is_entry:
                    if len(active_positions) >= MAX_POSITIONS:
                        print(f"   ⚠️ Skipping {symbol} {side.upper()} - Max positions reached ({MAX_POSITIONS})")
                        continue
                        
                    # Local Margin Check for entry signals
                    estimated_cost = (abs_delta * current_price) / leverage
                    
                    if estimated_cost > current_available_margin:
                        # Try to fit to remaining margin if it's worth it (min $10 margin)
                        if current_available_margin > 10.0:
                            print(f"   ⚠️ Insufficient Margin for full size (${estimated_cost:.2f}). Resizing to fit ${current_available_margin:.2f}...")
                            
                            # Calculate new amount to fit margin with 5% buffer
                            safe_margin = current_available_margin * 0.95
                            new_amount = (safe_margin * leverage) / current_price
                            
                            # Check if new amount is above min limit (approx)
                            if (new_amount * current_price) > 5.0: # Min notional usually $5
                                abs_delta = new_amount
                                print(f"      📉 Resized amount to {abs_delta:.4f}")
                            else:
                                print(f"      ❌ Remaining margin too small for valid order. Skipping.")
                                continue
                        else:
                            print(f"   ⚠️ Skipping {symbol} {side.upper()} - Insufficient Local Margin (${current_available_margin:.2f} < ${estimated_cost:.2f})")
                            continue

                print(f"\n⚡ EXECUTION: {side.upper()} {abs_delta:.4f} {symbol} | Reason: {signal_msg}")
                
                if not snapshot:
                    if not SIMULATION_MODE:
                        try:
                            current_available_margin = execute_trade_safely(
                                exchange, symbol, side, abs_delta, current_price, 
                                {'reduceOnly': True} if action.get('reduceOnly', False) else {},
                                current_available_margin, active_positions, BLACKLIST, signal_msg
                            )

                        except Exception as e:
                            err_msg = str(e)
                            print(f"   ❌ Order Failed for {symbol}: {err_msg}")
                            log_trade(datetime.now().isoformat(), symbol, side, abs_delta, current_price, signal_msg, f"FAILED: {err_msg}")
                            
                            # SELF-HEALING: Blacklist broken symbols
                            if "-1121" in err_msg or "-4140" in err_msg or "-1111" in err_msg:
                                print(f"   🚫 Blacklisting {symbol} (Invalid/Error)")
                                BLACKLIST.add(symbol)
                    else:
                        # SIMULATED EXECUTION
                        print(f"   📝 SIMULATED TRADE: {side.upper()} {abs_delta:.4f} {symbol} @ {current_price:.2f}")
                        # Simplified simulation for multi-symbol
                        if side == 'buy':
                            sim_balance -= (abs_delta * current_price * 0.0005) # Fee
                            active_positions[symbol] = {'amt': abs_delta, 'entry': current_price, 'pnl': 0.0}
                        else: # sell
                            sim_balance -= (abs_delta * current_price * 0.0005) # Fee
                            if symbol in active_positions:
                                del active_positions[symbol]
                            else:
                                active_positions[symbol] = {'amt': -abs_delta, 'entry': current_price, 'pnl': 0.0}
                        log_trade(datetime.now(), symbol, side, abs_delta, current_price, signal_msg, "SIMULATION_FILLED")
                else:
                    print(f"   [Snapshot] Order for {symbol} skipped.")
            
            # Update Dashboard State
            state = {
                'timestamp': datetime.now().isoformat(),
                'balance': usdt_balance,
                'available_balance': available_balance,
                'positions': active_positions,
                'market_scan': current_market_scan_data,
                'sentiment': global_sentiment,
                'blacklist': list(BLACKLIST),
                'realized_pnl': realized_pnl
            }
            with open('dashboard_state.json', 'w') as f:
                json.dump(state, f)
            
            # --- HISTORY TRACKING ---
            HISTORY_FILE = "balance_history.csv"
            total_open_pnl = sum(p['pnl'] for p in active_positions.values())
            
            file_exists = os.path.isfile(HISTORY_FILE)
            with open(HISTORY_FILE, mode='a', newline='') as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(['timestamp', 'balance', 'open_pnl', 'position_count', 'sentiment', 'realized_pnl'])
                writer.writerow([datetime.now().isoformat(), usdt_balance, total_open_pnl, len(active_positions), global_sentiment, realized_pnl])
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Scan Complete. Active Pos: {len(active_positions)} | Realized PnL: ${realized_pnl:.2f}")
            
            if snapshot: break
            time.sleep(POLL_INTERVAL)
            
        except KeyboardInterrupt:
            print("\nStopped by user.")
            break
        except Exception as e:
            print(f"\nMain Loop Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot', action='store_true', help='Run once and exit')
    args = parser.parse_args()
    run_bot(snapshot=args.snapshot)
