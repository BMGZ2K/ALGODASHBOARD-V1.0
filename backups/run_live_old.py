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
            'CRV/USDT': {'amount': 1, 'price': 4},
            'FTM/USDT': {'amount': 0, 'price': 4},
            'EOS/USDT': {'amount': 1, 'price': 3},
            'MATIC/USDT': {'amount': 0, 'price': 4},
            'DYDX/USDT': {'amount': 1, 'price': 3},
            'APE/USDT': {'amount': 0, 'price': 4},
            'CHZ/USDT': {'amount': 0, 'price': 5},
            'KAVA/USDT': {'amount': 1, 'price': 4},
            'XTZ/USDT': {'amount': 1, 'price': 3},
            'GALA/USDT': {'amount': 0, 'price': 5},
            'QNT/USDT': {'amount': 1, 'price': 2},
            'AAVE/USDT': {'amount': 1, 'price': 2},
            'EGLD/USDT': {'amount': 1, 'price': 2},
            'AXS/USDT': {'amount': 1, 'price': 3},
            'MANA/USDT': {'amount': 0, 'price': 4},
            'SAND/USDT': {'amount': 0, 'price': 4},
            'ICP/USDT': {'amount': 1, 'price': 2},
            'ETC/USDT': {'amount': 2, 'price': 2},
            'RUNE/USDT': {'amount': 1, 'price': 3},
            '1000PEPE/USDT': {'amount': 0, 'price': 7},
            '1000SHIB/USDT': {'amount': 0, 'price': 6},
            '1000FLOKI/USDT': {'amount': 0, 'price': 5},
            '1000BONK/USDT': {'amount': 0, 'price': 6}
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

def analyze_symbol(symbol, exchange, pos_data, usdt_balance, available_balance, is_spot, is_sim, global_sentiment, blacklist, params):
    try:
        # Fetch Data (Increased limit for slow indicators)
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=500)
        if not ohlcv: return None
        
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        current_price = df.iloc[-1]['close']
        
        # --- SMART CONFIG ---
        USE_HEIKIN_ASHI = True
        RISK_PER_TRADE = 0.02 # 2% Risk
        LEVERAGE_CAP = 5 # 5x Max Leverage
        
        # --- DONCHIAN CHANNEL (Trend Filter) ---
        # Using breakout_window from config (default 20)
        window = params.get('breakout_window', 20)
        df['donchian_high'] = df['high'].rolling(window=window).max()
        df['donchian_low'] = df['low'].rolling(window=window).min()
        
        donchian_high = df['donchian_high'].iloc[-2] # Previous candle to avoid lookahead
        donchian_low = df['donchian_low'].iloc[-2]
        
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
        score = 0
        trail_stop = 0.0 # For visualization
        current_pos = pos_data['amt']
        
        # Track Peak Price for Chandelier Exit
        # Initialize if not present (backward compatibility)
        if current_pos > 0:
            max_price = pos_data.get('max_price', pos_data['entry'])
            max_price = max(max_price, current_price)
            min_price = 0.0 # Not relevant for long
        elif current_pos < 0:
            min_price = pos_data.get('min_price', pos_data['entry'])
            min_price = min(min_price, current_price)
            max_price = 0.0 # Not relevant for short
        else:
            max_price = 0.0
            min_price = 0.0

        # EXIT LOGIC
        if current_pos != 0:
            atr_stop_mult = 2.0
            entry = pos_data['entry']
            pnl_per_unit = (current_price - entry) if current_pos > 0 else (entry - current_price)
            roi_pct = pnl_per_unit / entry
            
            # 1. Volume Climax Exit (Panic/Euphoria Catcher)
            # If volume explodes 3x avg and RSI is extreme, it's likely the top/bottom
            if current_vol > (vol_sma * 3.0):
                if current_pos > 0 and rsi_value > 80:
                    signal_msg = "EXIT_CLIMAX_PUMP"
                    action = {'symbol': symbol, 'side': 'sell', 'amount': abs(current_pos), 'price': current_price, 'reason': signal_msg, 'reduceOnly': True}
                elif current_pos < 0 and rsi_value < 20:
                    signal_msg = "EXIT_CLIMAX_DUMP"
                    action = {'symbol': symbol, 'side': 'buy', 'amount': abs(current_pos), 'price': current_price, 'reason': signal_msg, 'reduceOnly': True}

            # 2. Hard Take Profit (3.5x ATR) - Bank Big Wins
            # EVOLUTION: If ADX > 50 (Super Trend), DISABLE Hard TP to let it run!
            if not action and pnl_per_unit > (current_atr * 3.5):
                if current_adx < 50: # Only cap profit if trend isn't insane
                    signal_msg = "EXIT_TP_HARD"
                    side = 'sell' if current_pos > 0 else 'buy'
                    action = {'symbol': symbol, 'side': side, 'amount': abs(current_pos), 'price': current_price, 'reason': signal_msg, 'reduceOnly': True}
                else:
                    # Let it run! But maybe tighten trailing stop?
                    # The Profit Ratchet (Level 4) already handles this by tightening to 1.08x Entry.
                    pass
            
            # 3. Smart Trailing Stop (Chandelier + Profit Ratchet)
            elif not action:
                # DYNAMIC MULTIPLIER based on Profit Depth
                peak_pnl = (max_price - entry) if current_pos > 0 else (entry - min_price)
                
                # DYNAMIC ATR MULTIPLIER (Tighten as profit grows)
                atr_stop_mult = 2.5 # RELAXED DEFAULT (Was 2.0) - Give trades room to breathe!
                
                if peak_pnl > (current_atr * 1.0):
                    atr_stop_mult = 1.5 
                if peak_pnl > (current_atr * 2.0):
                    atr_stop_mult = 1.0
                if peak_pnl > (current_atr * 4.0):
                    atr_stop_mult = 0.5
                
                # Bollinger Band / RSI Overextension (Extreme Climax)
                # FIX: Only apply this tight stop if we are already in profit!
                # Otherwise we get stopped out instantly on high-momentum entries.
                if roi_pct > 0.01:
                    if current_pos > 0 and current_price > upper_bb and rsi_value > 75:
                         atr_stop_mult = 0.2 
                    elif current_pos < 0 and current_price < lower_bb and rsi_value < 25:
                         atr_stop_mult = 0.2

                # STAGNATION EXIT (Time-Based)
                # If trade is > 240 mins (4h) and PnL is negative, kill it.
                if 'entry_time' in pos_data:
                    try:
                        entry_dt = datetime.fromisoformat(pos_data['entry_time'])
                        duration_mins = (datetime.now() - entry_dt).total_seconds() / 60
                        if duration_mins > 240 and roi_pct < 0:
                            signal_msg = f"EXIT_STAGNATION (4h+ and Red)"
                            side = 'sell' if current_pos > 0 else 'buy'
                            action = {'symbol': symbol, 'side': side, 'amount': abs(current_pos), 'price': current_price, 'reason': signal_msg, 'reduceOnly': True}
                    except:
                        pass

                # SMART DCA (Defend High Quality Trades)
                # If trade is down > 2% but Trend is still valid, add to position (Max 1 add)
                # Check if we haven't added yet (using a flag or checking size vs base size)
                # Simplified: If size is small (initial entry) and condition met.
                # Assuming base size is approx risk_amt / stop_dist. We can check if 'dca_count' in pos_data.
                
                if not action and roi_pct < -0.02 and roi_pct > -0.06: # Down 2-6% (WIDENED)
                    # Only defend if Trend is still in our favor
                    trend_valid = (current_pos > 0 and current_trend == 1) or (current_pos < 0 and current_trend == -1)
                    
                    if trend_valid and 'dca_count' not in pos_data:
                        # Check RSI (Don't add if momentum is totally dead)
                        rsi_ok = (current_pos > 0 and rsi_value < 65) or (current_pos < 0 and rsi_value > 35)
                        
                        if rsi_ok:
                            signal_msg = "DCA_DEFENSE (Trend Valid)"
                            # Add 50% of current size
                            add_amt = abs(current_pos) * 0.5
                            side = 'buy' if current_pos > 0 else 'sell'
                            
                            # We need to pass 'dca_count' update to execute_trade. 
                            # For now, we'll handle it by checking size, but better to add a special reason.
                            action = {'symbol': symbol, 'side': side, 'amount': add_amt, 'price': current_price, 'reason': signal_msg, 'score': 8.5, 'is_dca': True}

                if not action:
                    # CALCULATE STOP PRICE (Chandelier Logic)
                    if current_pos > 0: # LONG
                        trail_stop = max_price - (current_atr * atr_stop_mult)
                        
                        # PROFIT RATCHET (Aggressive Locking)
                        # Level 1: Breakeven + Fees (0.8% ROI - Faster Safety)
                        if roi_pct > 0.008:
                            trail_stop = max(trail_stop, entry * 1.002)
                        # Level 1.5: Secure Small Win (1.5% ROI)
                        if roi_pct > 0.015:
                            trail_stop = max(trail_stop, entry * 1.005)
                        
                        # CHOPPY MARKET SCALP (If ADX < 25, take profit NOW)
                        if current_adx < 25 and roi_pct > 0.015:
                             signal_msg = f"EXIT_CHOP_SCALP (ROI {roi_pct*100:.1f}%)"
                             action = {'symbol': symbol, 'side': 'sell', 'amount': abs(current_pos), 'price': current_price, 'reason': signal_msg, 'reduceOnly': True}

                        # Level 2: Secure Small Win (2.5% ROI)
                        if roi_pct > 0.025:
                            trail_stop = max(trail_stop, entry * 1.01)
                        # Level 3: Secure Good Win (5% ROI)
                        if roi_pct > 0.05:
                            trail_stop = max(trail_stop, entry * 1.03)
                        # Level 4: Home Run (10% ROI)
                        if roi_pct > 0.10:
                            trail_stop = max(trail_stop, entry * 1.08)

                        if current_price < trail_stop:
                            signal_msg = f"EXIT_TRAIL_STOP (ROI {roi_pct*100:.1f}%)"
                            action = {'symbol': symbol, 'side': 'sell', 'amount': abs(current_pos), 'price': current_price, 'reason': signal_msg, 'reduceOnly': True}
                            
                    elif current_pos < 0: # SHORT
                        trail_stop = min_price + (current_atr * atr_stop_mult)
                        
                        # PROFIT RATCHET (Aggressive Locking)
                        # Level 1: Breakeven + Fees (0.8% ROI - Faster Safety)
                        if roi_pct > 0.008:
                            trail_stop = min(trail_stop, entry * 0.998)
                        # Level 1.5: Secure Small Win (1.5% ROI)
                        if roi_pct > 0.015:
                            trail_stop = min(trail_stop, entry * 0.995)
                        
                        # CHOPPY MARKET SCALP (If ADX < 25, take profit NOW)
                        if current_adx < 25 and roi_pct > 0.015:
                             signal_msg = f"EXIT_CHOP_SCALP (ROI {roi_pct*100:.1f}%)"
                             action = {'symbol': symbol, 'side': 'buy', 'amount': abs(current_pos), 'price': current_price, 'reason': signal_msg, 'reduceOnly': True}

                        # Level 2: Secure Small Win (2.5% ROI)
                        if roi_pct > 0.025:
                            trail_stop = min(trail_stop, entry * 0.99)
                        # Level 3: Secure Good Win (5% ROI)
                        if roi_pct > 0.05:
                            trail_stop = min(trail_stop, entry * 0.97)
                        # Level 4: Home Run (10% ROI)
                        if roi_pct > 0.10:
                            trail_stop = min(trail_stop, entry * 0.92)

                        if current_price > trail_stop:
                            signal_msg = f"EXIT_TRAIL_STOP (ROI {roi_pct*100:.1f}%)"
                            action = {'symbol': symbol, 'side': 'buy', 'amount': abs(current_pos), 'price': current_price, 'reason': signal_msg, 'reduceOnly': True}

                    
        # ENTRY LOGIC
        else:
            target_dir = 0
            
            # Adaptive Thresholds based on Global Sentiment & Config
            rsi_long_threshold = params.get('rsi_buy', 50)
            rsi_short_threshold = 100 - rsi_long_threshold
            
            if global_sentiment > 0.6: 
                rsi_long_threshold += 5 
            elif global_sentiment < 0.4: 
                rsi_short_threshold -= 5 
            
            # DYNAMIC SENTIMENT FILTER
            # In Strong Bull Market (Sent > 0.75), forbid weak Shorts (Score < 8)
            # In Strong Bear Market (Sent < 0.25), forbid weak Longs (Score < 8)
            allow_weak_short = global_sentiment < 0.75
            allow_weak_long = global_sentiment > 0.25

            # Regime Detection
            if current_adx > 20: # Trend (Relaxed to 20 to catch early moves)
                # Volume Filter (Stricter for Breakouts: > 1.2x SMA)
                if current_vol > (vol_sma * 0.8):
                    # 1. DONCHIAN BREAKOUT (New High/Low) - Strongest Signal
                    # Require Higher Volume for Breakout (1.5x) AND Major Trend Alignment
                    if current_price > donchian_high and current_vol > (vol_sma * 1.5) and slow_trend == 1:
                        target_dir = 1
                        signal_msg = "LONG_BREAKOUT_DONCHIAN"
                        score = 9.5
                    elif current_price < donchian_low and current_vol > (vol_sma * 1.5) and slow_trend == -1:
                        target_dir = -1
                        signal_msg = "SHORT_BREAKOUT_DONCHIAN"
                        score = 9.5
                    
                    # 2. STANDARD PULLBACK ENTRY (Must align with Slow Trend)
                    elif current_trend == slow_trend:
                        # Tighter RSI for Pullbacks (Buy dips, don't chase)
                        if current_trend == 1 and rsi_value < 55:
                            target_dir = 1
                            signal_msg = "LONG_TREND_ALIGNED"
                            score = 10
                        elif current_trend == -1 and rsi_value > 45:
                            target_dir = -1
                            signal_msg = "SHORT_TREND_ALIGNED"
                            score = 10
                            target_dir = -1
                            signal_msg = "SHORT_MOMENTUM_BREAKOUT"
                            score = 9
                    
                    # 3. TREND CONTINUATION (Extreme Sentiment Adaptation)
                    # If market is crashing/mooning, don't wait for deep pullbacks.
                    elif current_adx > 25:
                        # Extreme Bear: Sell minor rips
                        if global_sentiment < 0.2 and current_trend == -1 and slow_trend == -1:
                            # FIX: Don't sell if RSI is already too low (Oversold)
                            if rsi_value > 40 and rsi_value < 60: 
                                target_dir = -1
                                signal_msg = "SHORT_TREND_CONTINUATION"
                                score = 8.5
                        
                        # Extreme Bull: Buy minor dips
                        elif global_sentiment > 0.8 and current_trend == 1 and slow_trend == 1:
                            # FIX: Don't buy if RSI is already too high (Overbought)
                            if rsi_value < 60 and rsi_value > 40:
                                target_dir = 1
                                signal_msg = "LONG_TREND_CONTINUATION"
                                score = 8.5

            else: # Range / Squeeze
                # 1. VOLATILITY SQUEEZE BREAKOUT (High Profit)
                # Must align with Slow Trend to avoid fakeouts
                if current_width < width_threshold: 
                    if current_price > upper_bb and current_vol > vol_sma and slow_trend == 1:
                        target_dir = 1
                        signal_msg = "LONG_SQUEEZE_BREAKOUT"
                        score = 9
                    elif current_price < lower_bb and current_vol > vol_sma and slow_trend == -1:
                        target_dir = -1
                        signal_msg = "SHORT_SQUEEZE_BREAKOUT"
                        score = 9
                
                # REMOVED: Stochastic Scalping (Too risky in trends)
                # REMOVED: Mean Reversion (Catching falling knives)
                # We only want A+ Trend/Breakout setups.
            
            # DYNAMIC POSITION SIZING (Smart Margin)
            if target_dir != 0:
                # Boost Score with ADX (Trend Strength)
                score += (current_adx / 10.0)
                
                # Boost Score with Volatility (Prioritize Movers)
                volatility_pct = (current_atr / current_price) * 100
                score += volatility_pct
                
                # Dynamic Risk Sizing based on Score (ELITE ONLY MODE)
                if score >= 9.0:
                    risk_pct = 0.05 # 5% Risk for A+ Setups (High Conviction)
                elif score >= 8.0:
                    risk_pct = 0.03 # 3% Risk for Strong Setups
                else:
                    risk_pct = 0.0 # Skip anything below Score 8 (No weak trades)
                
                # Risk Amount
                risk_amt = usdt_balance * risk_pct
                
                # Stop Distance (Tighter: 1.5 ATR for better R:R)
                stop_dist = current_atr * 1.5
                if stop_dist == 0: stop_dist = current_price * 0.01 # Fallback
                
                # Quantity based on Risk
                qty_risk = risk_amt / stop_dist
                
                # Quantity based on Leverage Cap
                max_qty_lev = (usdt_balance * LEVERAGE_CAP) / current_price
                
                # Quantity based on Available Margin (Critical for "Insufficient Margin" fix)
                # Leave 5% buffer
                max_qty_margin = (available_balance * 0.95 * LEVERAGE_CAP) / current_price

                # MAX NOTIONAL CAP (Diversification Rule)
                # Limit single trade to 15% of Total Buying Power to allow multiple positions
                total_buying_power = usdt_balance * LEVERAGE_CAP
                max_notional_per_trade = total_buying_power * 0.15 
                max_qty_notional = max_notional_per_trade / current_price
                
                # Final Quantity (Min of all constraints)
                final_qty = min(qty_risk, max_qty_lev, max_qty_margin, max_qty_notional)
                
                # Ensure minimum notional (approx $6 for Binance)
                if (final_qty * current_price) < 6:
                    final_qty = 0 # Skip if too small
                
                if final_qty > 0:
                    side = 'buy' if target_dir == 1 else 'sell'
                    action = {'symbol': symbol, 'side': side, 'amount': final_qty, 'price': current_price, 'reason': signal_msg, 'score': score}

        return {
            'symbol': symbol,
            'price': current_price,
            'trend': current_trend,
            'rsi': rsi_value,
            'adx': current_adx,
            'signal': signal_msg,
            'position': current_pos,
            'pnl': pos_data['pnl'],
            'action': action,
            'score': score,
            'max_price': max_price,
            'min_price': min_price,
            'trail_stop': trail_stop
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
    'INJ/USDT', 'STX/USDT', 'IMX/USDT', 'GRT/USDT', 'SNX/USDT',
    'VET/USDT', 'THETA/USDT', 'LDO/USDT', 'TIA/USDT', 'SEI/USDT',
    'ORDI/USDT', 'FET/USDT', 'ALGO/USDT', 'FLOW/USDT', 'XLM/USDT',
    'CRV/USDT', '1000PEPE/USDT', 'RUNE/USDT', 'ETC/USDT', 'ICP/USDT',
    'SAND/USDT', 'MANA/USDT', 'AXS/USDT', 'EGLD/USDT', 'AAVE/USDT',
    'EOS/USDT', 'QNT/USDT', 'GALA/USDT', 'FTM/USDT', 'MATIC/USDT',
    'DYDX/USDT', 'APE/USDT', 'CHZ/USDT', 'KAVA/USDT', 'XTZ/USDT',
    '1000SHIB/USDT', '1000FLOKI/USDT', '1000BONK/USDT'
]

def execute_trade_safely(exchange, symbol, side, amount, price, params, current_margin, active_positions, blacklist, signal_msg):
    """
    Executes a trade with robust error handling, retries, and raw API calls.
    Updates active_positions and returns the updated current_margin.
    """
    attempts = 0
    executed = False
    final_amount = amount
    leverage = 5 # Synced with LEVERAGE_CAP
    max_attempts = 5
    
    while attempts < max_attempts and not executed:
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
            # Update active_positions immediately
            if params.get('reduceOnly', False):
                # Closing Position
                if symbol in active_positions:
                    del active_positions[symbol]
            else:
                # Opening / Adding Position
                if symbol in active_positions:
                    # DCA / Adding to existing
                    old_pos = active_positions[symbol]
                    old_amt = old_pos['amt']
                    old_entry = old_pos['entry']
                    
                    # Calculate new weighted average entry
                    total_cost = (abs(old_amt) * old_entry) + (final_amount * price)
                    new_total_amt = abs(old_amt) + final_amount
                    new_avg_entry = total_cost / new_total_amt
                    
                    # Update position
                    active_positions[symbol]['amt'] = new_total_amt if side == 'buy' else -new_total_amt
                    active_positions[symbol]['entry'] = new_avg_entry
                    active_positions[symbol]['dca_count'] = old_pos.get('dca_count', 0) + 1
                    print(f"      ➕ DCA Executed. New Entry: {new_avg_entry:.4f}")
                else:
                    # New Position
                    amt_signed = final_amount if side == 'buy' else -final_amount
                    active_positions[symbol] = {'amt': amt_signed, 'entry': price, 'pnl': 0.0, 'entry_time': datetime.now().isoformat(), 'dca_count': 0}
            
            # Update Local Margin (only if opening/increasing risk)
            if not params.get('reduceOnly', False):
                used_margin = (final_amount * price) / leverage
                current_margin -= used_margin
                print(f"      ℹ️  Margin Updated: ${current_margin:.2f} remaining")

        except Exception as order_e:
            err_msg = str(order_e).lower()
            last_error = err_msg # Capture for final report
            
            if "margin" in err_msg or "balance" in err_msg or "account has insufficient balance" in err_msg:
                print(f"      ⚠️ Insufficient Margin. Retrying with 50% size...")
                final_amount *= 0.5
                attempts += 1
                time.sleep(0.5 * (attempts + 1)) # Exponential backoff
                
                # ... (min amount check) ...
                
            elif "-2022" in err_msg or "reduceonly" in err_msg:
                # ... (existing reduceOnly logic) ...
                attempts += 1
                time.sleep(0.5 * (attempts + 1))

            elif "-1111" in err_msg or "precision" in err_msg:
                print(f"      ⚠️ Precision Error. Attempting to round to integer...")
                final_amount = int(final_amount)
                attempts += 1
                time.sleep(0.5 * (attempts + 1))
            
            elif "-4140" in err_msg or "invalid symbol status" in err_msg or "-1121" in err_msg:
                print(f"      🚫 Symbol {symbol} is in Invalid Status. Blacklisting...")
                blacklist.add(symbol)
                last_error = "Blacklisted: Invalid Symbol"
                break
            
            elif "-4005" in err_msg or "quantity greater than max quantity" in err_msg:
                print(f"      ⚠️ Max Quantity Exceeded. Retrying with 50% size...")
                final_amount *= 0.5
                attempts += 1
                time.sleep(0.5 * (attempts + 1))

            elif "argument of type 'nonetype' is not iterable" in err_msg:
                print(f"      ⚠️ CCXT NoneType Error. Retrying...")
                attempts += 1
                time.sleep(0.5 * (attempts + 1))
            else:
                # Other errors (e.g. network)
                print(f"      ❌ Order Error: {err_msg}")
                attempts += 1
                time.sleep(0.5 * (attempts + 1))
    
    if not executed:
        print(f"   ❌ Order Failed for {symbol} after {attempts} retries. Last Error: {last_error}")
        log_trade(datetime.now().isoformat(), symbol, side, amount, price, signal_msg, f"FAILED: {last_error}")
        
        # Auto-Blacklist on persistent unknown failures
        if attempts >= max_attempts:
             print(f"      🚫 Persistent Failures. Blacklisting {symbol} temporarily.")
             blacklist.add(symbol)

    return current_margin

def run_bot(snapshot=False):
    # --- MULTI-SYMBOL CONFIGURATION ---
    MAX_POSITIONS = 20 # Increased exposure for 36 pairs
    BLACKLIST = set() # Self-healing mechanism for problematic symbols
    
    # Load Blacklist from State
    if os.path.exists('dashboard_state.json'):
        try:
            with open('dashboard_state.json', 'r') as f:
                saved_state = json.load(f)
                saved_blacklist = saved_state.get('blacklist', [])
                BLACKLIST = set(saved_blacklist)
                if BLACKLIST:
                    print(f"   🚫 Loaded Blacklist: {BLACKLIST}")
        except Exception as e:
            print(f"   ⚠️ Blacklist Load Error: {e}")

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
            try:
                # DYNAMIC MARKET LOADING (The "Evolution")
                # Instead of hardcoding, we trust the exchange but sanitize the result
                print("   🔄 Loading Exchange Markets...")
                markets = exchange.load_markets()
                
                # Filter and Map SYMBOLS to Exchange Precision
                for sym in SYMBOLS:
                    if sym in markets:
                        m = markets[sym]
                        # Ensure we have the correct precision structure
                        # CCXT unifies this, but we double check
                        prec = m.get('precision', {})
                        if 'amount' not in prec: prec['amount'] = 1
                        if 'price' not in prec: prec['price'] = 4
                        
                        # Ensure critical keys exist for CCXT internals
                        if 'option' not in m: m['option'] = False
                        if 'contract' not in m: m['contract'] = True
                        if 'linear' not in m: m['linear'] = True
                        
                        # Limits
                        limits = m.get('limits', {})
                        min_amt = limits.get('amount', {}).get('min', 0.001)
                        
                        # Update our internal map if needed, but relying on CCXT's 'markets' is better
                        # We just print to confirm it's found
                        # print(f"      ✅ Loaded {sym}: Prec Amt {prec['amount']}, Min {min_amt}")
                    else:
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
                
                for sym in SYMBOLS:
                    # exchange.set_leverage(2, sym) # This also triggers margin checks sometimes
                    # Raw leverage set
                    exchange.fapiPrivatePostLeverage({
                        'symbol': sym.replace('/', ''),
                        'leverage': 5
                    })
                print("   ✅ Leverage set to 5x (Raw) for all symbols")
                
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
    POLL_INTERVAL = 5 # Scan every 5s (Turbo Mode)
    
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
        print(f"   ⚠️ Could not fetch initial balance: {e}")
        initial_balance = 1000.0 # Fallback

    print(f"   ⏱️  Poll Interval: {POLL_INTERVAL}s")
    
    last_sync_time = datetime.now() # Initialize sync timer

    # State Tracking for Dashboard
    system_state = {sym: {'price': 0.0, 'trend': 0, 'rsi': 0, 'adx': 0, 'signal': 'IDLE', 'pos': 0.0, 'pnl': 0.0} for sym in SYMBOLS}
    
    # --- MAIN LOOP ---
    global_sentiment = 0.5 # Neutral start
    COMMAND_FILE = "bot_commands.json"
    
    # SMART AUTO-PILOT CONFIG
    # No external config file, just pure logic
    MAX_POSITIONS = 20
    
    # Cooldown Tracker
    last_exit_times = {}
    COOLDOWN_MINUTES = 15

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
            
            # --- PERSISTENCE MERGE FIX ---
            # Load previous state to recover max_price/min_price for Trailing Stops
            if os.path.exists('dashboard_state.json'):
                try:
                    with open('dashboard_state.json', 'r') as f:
                        saved_state = json.load(f)
                        saved_positions = saved_state.get('positions', {})
                        
                        for sym, pos in active_positions.items():
                            if sym in saved_positions:
                                # Restore peak prices if the position is still open
                                # We assume if symbol matches, it's the same position (simplified)
                                saved_p = saved_positions[sym]
                                if 'max_price' in saved_p:
                                    pos['max_price'] = saved_p['max_price']
                                if 'min_price' in saved_p:
                                    pos['min_price'] = saved_p['min_price']
                except Exception as e:
                    print(f"   ⚠️ State Restore Error: {e}")
            # -----------------------------
            
            print(f"\n--- 🔎 Scan ({len(ACTIVE_SYMBOLS)} Pairs) | Sent: {global_sentiment:.2f} | PnL: ${realized_pnl:.2f} | Margin: ${available_balance:.2f} ---")
            
            # 2. Scan & Execute for Each Symbol
            proposed_actions = []
            current_market_scan_data = {}
            current_trends = [] # For sentiment calculation

            # Load Strategy Config
            strategy_params = load_strategy_config("Hybrid_Futures_2x_LongShort")
            
            for symbol in ACTIVE_SYMBOLS:
                current_pos_data = active_positions.get(symbol, {'amt': 0.0, 'entry': 0.0, 'pnl': 0.0})
                analysis_result = analyze_symbol(symbol, exchange, current_pos_data, usdt_balance, available_balance, IS_SPOT_MODE, SIMULATION_MODE, global_sentiment, BLACKLIST, strategy_params)
                
                if analysis_result:
                    # Update Position Memory (Max/Min Price for Chandelier Exit)
                    if symbol in active_positions:
                        active_positions[symbol]['max_price'] = analysis_result.get('max_price', 0.0)
                        active_positions[symbol]['min_price'] = analysis_result.get('min_price', 0.0)
                        active_positions[symbol]['trail_stop'] = analysis_result.get('trail_stop', 0.0)

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

            # 3. Prioritize and Execute Actions (Sorted by Score)
            # Track margin locally to prevent multiple orders from exhausting balance simultaneously
            current_available_margin = available_balance
            leverage = 5 # Synced with LEVERAGE_CAP
            
            # CIRCUIT BREAKER (Stop trading if drawdown > 25%)
            drawdown_pct = (initial_balance - usdt_balance) / initial_balance
            if drawdown_pct > 0.25: # Increased to 25% to allow for recovery
                print(f"🚨 CIRCUIT BREAKER TRIGGERED: Drawdown -{drawdown_pct*100:.2f}% exceeds limit. Halting trading.")
                
                # Update Dashboard State even if Halted
                state = {
                    'timestamp': datetime.now().isoformat(),
                    'balance': usdt_balance,
                    'available_balance': current_available_margin,
                    'positions': active_positions,
                    'market_scan': {},
                    'sentiment': global_sentiment,
                    'blacklist': list(BLACKLIST),
                    'realized_pnl': realized_pnl,
                    'status': f"HALTED: Drawdown {drawdown_pct*100:.1f}%"
                }
                
                temp_file = "dashboard_state.json.tmp"
                with open(temp_file, 'w') as f:
                    json.dump(state, f)
                os.replace(temp_file, 'dashboard_state.json')
                
                time.sleep(60)
                continue

            # PERIODIC SYNC (Every 5 mins)
            # Force refresh positions from exchange to fix ghost/stuck trades
            if (datetime.now() - last_sync_time).total_seconds() > 300:
                print("   🔄 Performing Periodic Position Sync...")
                try:
                    # Re-fetch all positions
                    fresh_positions = {}
                    raw_pos = exchange.fapiPrivateV2GetAccount()['positions']
                    for p in raw_pos:
                        amt = float(p['positionAmt'])
                        if amt != 0:
                            sym = p['symbol']
                            # Convert symbol back to slash format if needed, or keep raw
                            # Our active_positions uses 'BTC/USDT', raw uses 'BTCUSDT'
                            # We need to map it back.
                            # Simple hack: find matching symbol in SYMBOLS list
                            slash_sym = next((s for s in SYMBOLS if s.replace('/', '') == sym), sym)
                            
                            entry_p = float(p['entryPrice'])
                            u_pnl = float(p['unrealizedProfit'])
                            
                            # Preserve local state if exists (max_price, trail_stop, entry_time)
                            if slash_sym in active_positions:
                                fresh_positions[slash_sym] = active_positions[slash_sym]
                                fresh_positions[slash_sym]['amt'] = amt
                                fresh_positions[slash_sym]['pnl'] = u_pnl
                            else:
                                # Try to estimate entry time or default to now
                                # Ideally we'd fetch order history, but for now:
                                fresh_positions[slash_sym] = {
                                    'amt': amt, 
                                    'entry': entry_p, 
                                    'pnl': u_pnl, 
                                    'entry_time': datetime.now().isoformat() # Default for truly new discoveries
                                }
                    
                    active_positions = fresh_positions
                    last_sync_time = datetime.now()
                    print(f"   ✅ Sync Complete. Active Positions: {len(active_positions)}")
                except Exception as e:
                    print(f"   ⚠️ Sync Failed: {e}")
            
            # Sort actions by score (descending) to prioritize best setups
            proposed_actions.sort(key=lambda x: x.get('score', 0), reverse=True)

            for action in proposed_actions:
                symbol = action['symbol']
                side = action['side']
                abs_delta = action['amount']
                current_price = action['price']
                signal_msg = action['reason']
                score = action.get('score', 0)

                # Check if we are already at MAX_POSITIONS and this is an entry signal
                # Check if this trade INCREASES risk (Entry or Adding)
                current_pos_amt = current_market_scan_data[symbol]['pos']
                is_increasing_risk = (side == 'buy' and current_pos_amt >= 0) or \
                                     (side == 'sell' and current_pos_amt <= 0)
                
                # COOLDOWN CHECK (Prevent Churning)
                if is_increasing_risk and current_pos_amt == 0:
                    last_exit = last_exit_times.get(symbol)
                    if last_exit:
                        elapsed_mins = (datetime.now() - last_exit).total_seconds() / 60
                        if elapsed_mins < COOLDOWN_MINUTES:
                            print(f"   ⏳ Cooldown Active for {symbol} ({elapsed_mins:.1f}m < {COOLDOWN_MINUTES}m). Skipping.")
                            continue

                if is_increasing_risk:
                    # Only check max positions for NEW positions
                    if current_pos_amt == 0 and len(active_positions) >= MAX_POSITIONS:
                        print(f"   ⚠️ Skipping {symbol} {side.upper()} - Max positions reached ({MAX_POSITIONS})")
                        continue
                        
                    # Local Margin Check for entry signals
                    estimated_cost = (abs_delta * current_price) / leverage
                    
                    if estimated_cost > current_available_margin:
                        # ROTATION LOGIC
                        score = action.get('score', 0)
                        if len(active_positions) > 0:
                            victim_symbol = None
                            
                            # Find weakest position
                            candidates = [s for s in active_positions if s != symbol]
                            if candidates:
                                weakest_sym = min(candidates, key=lambda s: active_positions[s]['pnl'])
                                weakest_pnl = active_positions[weakest_sym]['pnl']
                                
                                # CRITERIA 1: High Priority (Score >= 9) -> Sacrifice Stagnant/Small Winners
                                if score >= 9 and weakest_pnl < 5.0:
                                    victim_symbol = weakest_sym
                                    print(f"   ⚠️ High Priority (Score {score}) > Weakest ({weakest_sym} ${weakest_pnl:.2f})")
                                
                                # CRITERIA 2: Strong Priority (Score >= 8) -> Sacrifice Losers & Stagnant
                                elif score >= 8 and weakest_pnl < 1.0:
                                    victim_symbol = weakest_sym
                                    print(f"   ⚠️ Strong Priority (Score {score}) > Stagnant/Loser ({weakest_sym} ${weakest_pnl:.2f})")
                            
                            if victim_symbol:
                                victim_data = active_positions[victim_symbol]
                                print(f"      🔄 Sacrificing {victim_symbol} (PnL: ${victim_data['pnl']:.2f}) for {symbol}...")
                                
                                # Close Victim
                                try:
                                    # Raw close
                                    v_amt = abs(victim_data['amt'])
                                    v_side = 'SELL' if victim_data['amt'] > 0 else 'BUY'
                                    
                                    # Precision
                                    v_prec = exchange.markets[victim_symbol]['precision']['amount']
                                    v_qty_str = "{:.{}f}".format(v_amt, v_prec)
                                    
                                    exchange.fapiPrivatePostOrder({
                                        'symbol': victim_symbol.replace('/', ''),
                                        'side': v_side,
                                        'type': 'MARKET',
                                        'quantity': v_qty_str,
                                        'reduceOnly': 'true'
                                    })
                                    
                                    print(f"      ✅ Closed {victim_symbol}. Freeing margin...")
                                    
                                    # Estimate released margin (approx)
                                    released_margin = (v_amt * active_positions[victim_symbol]['entry']) / leverage
                                    current_available_margin += released_margin
                                    del active_positions[victim_symbol]
                                    
                                except Exception as e:
                                    print(f"      ❌ Rotation Failed: {e}")

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
                else:
                    print(f"   ℹ️  Reducing Risk for {symbol} (Pos: {current_pos_amt}). Skipping Margin Check.")

                print(f"\n⚡ EXECUTION: {side.upper()} {abs_delta:.4f} {symbol} | Reason: {signal_msg}")
                
                if not snapshot:
                    if not SIMULATION_MODE:
                        try:
                            current_available_margin = execute_trade_safely(
                                exchange, symbol, side, abs_delta, current_price, 
                                {'reduceOnly': True} if action.get('reduceOnly', False) else {},
                                current_available_margin, active_positions, BLACKLIST, signal_msg
                            )
                            
                            # Update Cooldown on Exit
                            if action.get('reduceOnly', False):
                                last_exit_times[symbol] = datetime.now()
                                print(f"   ❄️ Cooldown started for {symbol}")

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
            
            # Update Dashboard State (Atomic Write)
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
            
            # --- WRONG WAY CORRECTOR (Smart Sentiment Stop) ---
            # If we are holding a position against a strong market trend and it's losing, cut it early.
            for sym in list(active_positions.keys()):
                pos = active_positions[sym]
                roi = (pos['pnl'] / (abs(pos['amt']) * pos['entry'])) if pos['entry'] > 0 else 0
                
                # Case 1: Holding LONG in Deep Bear Market
                if global_sentiment < 0.25 and pos['amt'] > 0 and roi < -0.015:
                    print(f"   📉 SENTIMENT MISMATCH: {sym} is LONG in Bear Market (Sent {global_sentiment:.2f}) with ROI {roi*100:.2f}%. Closing...")
                    try:
                        # Raw API Close
                        v_amt = abs(pos['amt'])
                        v_side = 'SELL'
                        v_prec = exchange.markets[sym]['precision']['amount']
                        v_qty_str = "{:.{}f}".format(v_amt, v_prec)
                        
                        exchange.fapiPrivatePostOrder({
                            'symbol': sym.replace('/', ''),
                            'side': v_side,
                            'type': 'MARKET',
                            'quantity': v_qty_str,
                            'reduceOnly': 'true'
                        })
                        del active_positions[sym]
                        print(f"      ✅ Closed Wrong-Way Trade {sym}")
                    except Exception as e:
                        print(f"      ❌ Failed to close {sym}: {e}")
                
                # Case 2: Holding SHORT in Strong Bull Market
                elif global_sentiment > 0.75 and pos['amt'] < 0 and roi < -0.015:
                    print(f"   📈 SENTIMENT MISMATCH: {sym} is SHORT in Bull Market (Sent {global_sentiment:.2f}) with ROI {roi*100:.2f}%. Closing...")
                    try:
                        # Raw API Close
                        v_amt = abs(pos['amt'])
                        v_side = 'BUY'
                        v_prec = exchange.markets[sym]['precision']['amount']
                        v_qty_str = "{:.{}f}".format(v_amt, v_prec)
                        
                        exchange.fapiPrivatePostOrder({
                            'symbol': sym.replace('/', ''),
                            'side': v_side,
                            'type': 'MARKET',
                            'quantity': v_qty_str,
                            'reduceOnly': 'true'
                        })
                        del active_positions[sym]
                        print(f"      ✅ Closed Wrong-Way Trade {sym}")
                    except Exception as e:
                        print(f"      ❌ Failed to close {sym}: {e}")

            # --- STALE TRADE CLEANUP ---
            # If a position is open for > 4 hours and PnL is < 0.5%, close it to free margin.
            current_time = datetime.now()
            for sym in list(active_positions.keys()):
                pos = active_positions[sym]
                # We need entry_time. If not present, assume now (soft start)
                if 'entry_time' not in pos:
                    pos['entry_time'] = current_time.isoformat()
                
                entry_t = datetime.fromisoformat(pos['entry_time'])
                duration_hours = (current_time - entry_t).total_seconds() / 3600
                
                # Criteria: > 4 hours and ROI < 0.5% (Stagnant)
                roi = (pos['pnl'] / (pos['amt'] * pos['entry'])) if pos['entry'] > 0 else 0
                if duration_hours > 4.0 and roi < 0.005:
                    print(f"   ⏳ STALE TRADE: {sym} open for {duration_hours:.1f}h with low ROI ({roi*100:.2f}%). Closing...")
                    try:
                        # Execute Close (Raw API)
                        v_amt = abs(pos['amt'])
                        v_side = 'SELL' if pos['amt'] > 0 else 'BUY'
                        v_prec = exchange.markets[sym]['precision']['amount']
                        v_qty_str = "{:.{}f}".format(v_amt, v_prec)
                        
                        exchange.fapiPrivatePostOrder({
                            'symbol': sym.replace('/', ''),
                            'side': v_side,
                            'type': 'MARKET',
                            'quantity': v_qty_str,
                            'reduceOnly': 'true'
                        })
                        del active_positions[sym]
                        print(f"      ✅ Closed Stale Trade {sym}")
                    except Exception as e:
                        print(f"      ❌ Failed to close stale {sym}: {e}")
                
                # Criteria: > 6 hours and PnL < 0 (Zombie/Loser) - CUT LOSSES
                elif duration_hours > 6.0 and pos['pnl'] < 0:
                    print(f"   🧟 ZOMBIE TRADE: {sym} open for {duration_hours:.1f}h with NEGATIVE PnL (${pos['pnl']:.2f}). Cutting loss...")
                    try:
                        # Execute Close (Raw API)
                        v_amt = abs(pos['amt'])
                        v_side = 'SELL' if pos['amt'] > 0 else 'BUY'
                        v_prec = exchange.markets[sym]['precision']['amount']
                        v_qty_str = "{:.{}f}".format(v_amt, v_prec)
                        
                        exchange.fapiPrivatePostOrder({
                            'symbol': sym.replace('/', ''),
                            'side': v_side,
                            'type': 'MARKET',
                            'quantity': v_qty_str,
                            'reduceOnly': 'true'
                        })
                        del active_positions[sym]
                        print(f"      ✅ Killed Zombie Trade {sym}")
                    except Exception as e:
                        print(f"      ❌ Failed to kill zombie {sym}: {e}")

            print(f"   💤 Cycle Complete. Active: {len(active_positions)} | Margin: ${available_balance:.2f} | Waiting...")

            # Update Dashboard State (Atomic Write)
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
            
            temp_file = "dashboard_state.json.tmp"
            with open(temp_file, 'w') as f:
                json.dump(state, f)
            os.replace(temp_file, 'dashboard_state.json')
            
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
