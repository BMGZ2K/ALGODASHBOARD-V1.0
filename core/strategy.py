import pandas as pd
import os
import ast
from datetime import datetime
from .indicators import calculate_indicators
from .config import LEVERAGE_CAP, DEFAULT_STRATEGY_CONFIG, RISK_PER_TRADE, MAX_POSITIONS



def load_strategy_config(strategy_name):
    path = f"config/strategies/{strategy_name}_config.txt"
    if not os.path.exists(path):
        return DEFAULT_STRATEGY_CONFIG
    with open(path, 'r') as f:
        return ast.literal_eval(f.read())

def analyze_symbol(symbol, exchange, pos_data, usdt_balance, available_balance, is_spot, is_sim, global_sentiment, blacklist, params, funding_rate=0.0):
    try:
        # Fetch Data (Increased limit for slow indicators)
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=500)
        if not ohlcv: return None
        
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # Calculate Indicators
        inds = calculate_indicators(df, params)
        
        # Unpack Indicators
        current_price = inds['current_price']
        current_atr = inds['current_atr']
        rsi_value = inds['rsi_value']
        rsi_smooth = inds.get('rsi_smooth', rsi_value) # Use smoothed for entries
        current_adx = inds['current_adx']
        current_trend = inds['current_trend']
        confirmed_trend = inds.get('confirmed_trend', current_trend)
        slow_trend = inds['slow_trend']
        confirmed_slow_trend = inds.get('confirmed_slow_trend', slow_trend)
        lower_bb = inds['lower_bb']
        upper_bb = inds['upper_bb']
        current_width = inds['current_width']
        width_threshold = inds['width_threshold']
        current_vol = inds['current_vol']
        vol_sma = inds['vol_sma']
        
        # --- VOLUME PROJECTION (Fix for Incomplete Candles) ---
        # Project volume to end of 5m candle to compare fairly with SMA
        current_time = datetime.now()
        seconds_elapsed = (current_time.minute % 5) * 60 + current_time.second
        
        # Fix: Cap projection and ignore first minute for extreme signals
        if seconds_elapsed < 60:
            # Too early to project accurately, use raw but don't multiply wildly
            projected_vol = current_vol 
        elif seconds_elapsed < 150:
            # Conservative projection in first half
            # Cap multiplier to 3x to prevent early spikes
            mult = min(300 / seconds_elapsed, 3.0)
            projected_vol = current_vol * mult * 0.8
        else:
            projected_vol = current_vol * (300 / seconds_elapsed)
            
        stoch_k = df.iloc[-1]['stoch_k'] if not pd.isna(df.iloc[-1]['stoch_k']) else 50.0
        stoch_d = df.iloc[-1]['stoch_d'] if not pd.isna(df.iloc[-1]['stoch_d']) else 50.0
        
        # Calculate previous values for logic continuity
        prev_stoch_k = df.iloc[-2]['stoch_k'] if len(df) > 1 and not pd.isna(df.iloc[-2]['stoch_k']) else stoch_k
        prev_stoch_d = df.iloc[-2]['stoch_d'] if len(df) > 1 and not pd.isna(df.iloc[-2]['stoch_d']) else stoch_d
        donchian_high = inds['donchian_high']
        donchian_low = inds['donchian_low']
        ema_200 = inds['ema_200']
        chop = inds['chop']
        
        # Market Structure
        lowest_10 = inds['lowest_10']
        highest_10 = inds['highest_10']
        rsi_lowest_10 = inds['rsi_lowest_10']
        rsi_highest_10 = inds['rsi_highest_10']

        # Strategy Logic
        signal_msg = "WAIT"
        action = None
        score = 0
        trail_stop = pos_data.get('trail_stop', 0.0) # Retrieve previous trail stop
        current_pos = pos_data['amt']
        
        # Trend Bias (EMA 200 Filter)
        # Price > EMA 200 = Bullish Bias (Prefer Longs)
        # Price < EMA 200 = Bearish Bias (Prefer Shorts)
        bullish_bias = current_price > ema_200
        bearish_bias = current_price < ema_200
        
        # Track Peak Price for Chandelier Exit
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

        # Calculate Duration
        entry_time = pos_data.get('entry_time')
        duration_hours = 0.0
        if entry_time:
            try:
                et = datetime.fromisoformat(entry_time)
                duration_hours = (datetime.now() - et).total_seconds() / 3600
            except: pass

        # ADX Slope Calculation (Trend Strength Momentum)
        prev_adx = inds.get('prev_adx', current_adx) # Fallback if not available
        adx_slope = current_adx - prev_adx

        # --- VPA (Volume Price Analysis) ---
        # Detect genuine buying/selling pressure vs churn
        open_price = df['open'].iloc[-1]
        close_price = df['close'].iloc[-1]
        high_price = df['high'].iloc[-1]
        low_price = df['low'].iloc[-1]
        
        body_size = abs(close_price - open_price)
        candle_range = high_price - low_price
        spread_pct = body_size / candle_range if candle_range > 0 else 0.0
        
        vpa_confirmed = False
        # Wide Spread Candle (> 60% body) + High Volume (> 1.2x Avg) = Valid Move
        if spread_pct > 0.6 and projected_vol > (vol_sma * 1.2):
            vpa_confirmed = True
            
        # Churn/Indecision: Narrow spread + High Volume
        is_churn = spread_pct < 0.3 and projected_vol > (vol_sma * 1.5)

        # EXIT LOGIC
        if current_pos != 0:
            atr_stop_mult = 2.0
            entry = pos_data['entry']
            pnl_per_unit = (current_price - entry) if current_pos > 0 else (entry - current_price)
            roi_pct = pnl_per_unit / entry if entry > 0 else 0
            
            # Calculate Peak PnL for Trailing Stops
            peak_pnl = (max_price - entry) if current_pos > 0 else (entry - min_price)
            # 1. Volume Climax Exit (Panic/Euphoria Catcher)
            if projected_vol > (vol_sma * 3.0):
                if current_pos > 0 and rsi_value > 80:
                    signal_msg = "EXIT_CLIMAX_PUMP"
                    action = {'symbol': symbol, 'side': 'sell', 'amount': abs(current_pos), 'price': current_price, 'reason': signal_msg, 'reduceOnly': True}
                elif current_pos < 0 and rsi_value < 20:
                    signal_msg = "EXIT_CLIMAX_DUMP"
                    action = {'symbol': symbol, 'side': 'buy', 'amount': abs(current_pos), 'price': current_price, 'reason': signal_msg, 'reduceOnly': True}

            # 2. Dynamic Hard Take Profit (Volatility & Momentum Adjusted)
            # Base TP starts at 3.5 ATR.
            # If Trend is Strong (ADX > 30), we extend the TP to let it run.
            # If Volatility is expanding (Width increasing), we also extend.
            
            base_tp_mult = 3.5
            
            # Momentum Boost
            if current_adx > 50: base_tp_mult = 6.0 # Super Trend
            elif current_adx > 30: base_tp_mult = 4.5 # Strong Trend
            
            # Volatility Boost (Bollinger Band Width expansion)
            if current_width > width_threshold:
                 base_tp_mult += 1.0
            
            tp_price_dist = current_atr * base_tp_mult
            
            # PARTIAL TAKE PROFIT (Scale Out)
            # If we have good profit (> 2.0 ATR) but not yet at Hard TP, and RSI is getting hot, scale out 50%.
            tp_count = pos_data.get('tp_count', 0)
            if not action and tp_count == 0 and pnl_per_unit > (current_atr * 2.0):
                 # Check for exhaustion signs
                 is_hot = (current_pos > 0 and rsi_value > 75) or (current_pos < 0 and rsi_value < 25)
                 if is_hot:
                     signal_msg = "PARTIAL_TP_SCALE_OUT (Secure Gains)"
                     side = 'sell' if current_pos > 0 else 'buy'
                     # Close 50%
                     qty_close = abs(current_pos) * 0.5
                     action = {'symbol': symbol, 'side': side, 'amount': qty_close, 'price': current_price, 'reason': signal_msg, 'reduceOnly': True, 'is_tp': True}

            if not action and pnl_per_unit > tp_price_dist:
                # Only exit if momentum is fading or RSI is extreme
                # This prevents exiting too early in a parabolic move
                is_extreme = (current_pos > 0 and rsi_value > 85) or (current_pos < 0 and rsi_value < 15)
                momentum_fading = (current_pos > 0 and rsi_value < rsi_smooth) or (current_pos < 0 and rsi_value > rsi_smooth)
                
                if is_extreme or (current_adx < 25 and momentum_fading):
                    signal_msg = f"EXIT_TP_DYNAMIC ({base_tp_mult:.1f}x ATR)"
                    side = 'sell' if current_pos > 0 else 'buy'
                    action = {'symbol': symbol, 'side': side, 'amount': abs(current_pos), 'price': current_price, 'reason': signal_msg, 'reduceOnly': True}
            
            # 3. Trend Reversal Exit (Immediate Bail)
            elif not action:
                # Only exit on reversal if the new trend has some strength (ADX > 20)
                # Otherwise, it might just be a chop flip.
                if (current_pos > 0 and current_trend == -1) or (current_pos < 0 and current_trend == 1):
                     if current_adx > 20:
                         signal_msg = "EXIT_TREND_REVERSAL"
                         side = 'sell' if current_pos > 0 else 'buy'
                         action = {'symbol': symbol, 'side': side, 'amount': abs(current_pos), 'price': current_price, 'reason': signal_msg, 'reduceOnly': True}

            # 4. Smart Trailing Stop (Chandelier + ATR Ratchet)
            elif not action:
                # DYNAMIC ATR MULTIPLIER (Tighten as profit grows)
                atr_stop_mult = 2.5 # RELAXED DEFAULT
                
                if peak_pnl > (current_atr * 1.0):
                    atr_stop_mult = 1.5 
                if peak_pnl > (current_atr * 2.0):
                    atr_stop_mult = 1.0
                if peak_pnl > (current_atr * 4.0):
                    atr_stop_mult = 0.5
                
                # Bollinger Band / RSI Overextension (Extreme Climax)
                if roi_pct > 0.01:
                    if current_pos > 0 and current_price > upper_bb and rsi_value > 75:
                         atr_stop_mult = 0.2 
                    elif current_pos < 0 and current_price < lower_bb and rsi_value < 25:
                         atr_stop_mult = 0.2


                # PYRAMIDING (Press Winners - Maximize Profit)
                # If we are winning (> 2% ROI) and Trend is Strong (ADX > 30), add to position.
                if not action and roi_pct > 0.02:
                    # Trend Confirmation
                    trend_valid = (current_pos > 0 and current_trend == 1) or (current_pos < 0 and current_trend == -1)
                    
                    # Check Max Pyramids (Allow 2 adds)
                    dca_count = pos_data.get('dca_count', 0)
                    
                    if trend_valid and dca_count < 2 and current_adx > 30 and adx_slope > 0.05:
                        # Check RSI (Room to run?)
                        rsi_ok = (current_pos > 0 and rsi_value < 70) or (current_pos < 0 and rsi_value > 30)
                        
                        # Check Overextension (Don't add if too far from EMA)
                        dist_atr = abs(current_price - ema_200)
                        is_overextended = dist_atr > (current_atr * 4)
                        
                        # Require higher ROI buffer (2.5%) to finance the risk
                        if rsi_ok and not is_overextended and roi_pct > 0.025:
                            signal_msg = "PYRAMID_ADD (Strong Trend + Mom)"
                            # Add 50% of current size
                            add_amt = abs(current_pos) * 0.5
                            side = 'buy' if current_pos > 0 else 'sell'
                            
                            action = {'symbol': symbol, 'side': side, 'amount': add_amt, 'price': current_price, 'reason': signal_msg, 'score': 9.0, 'is_dca': True}

            # 4. DYNAMIC SCALP EXIT (RSI Extremes)
            # Only if trend is NOT super strong (ADX < 40). 
            # If ADX > 40, we let it ride because RSI can stay overbought for a long time.
            # 4. DYNAMIC SCALP EXIT (RSI Extremes)
            # Only if trend is WEAK (ADX < 30). 
            if not action and roi_pct > 0.01:
                # Aggressive Scalp in Chop (ADX < 25)
                if current_adx < 25:
                    if (current_pos > 0 and rsi_smooth > 70) or (current_pos < 0 and rsi_smooth < 30):
                        signal_msg = f"EXIT_SCALP_CHOP (RSI {rsi_smooth:.1f}, Weak ADX)"
                        side = 'sell' if current_pos > 0 else 'buy'
                        action = {'symbol': symbol, 'side': side, 'amount': abs(current_pos), 'price': current_price, 'reason': signal_msg, 'reduceOnly': True}
                
                # Standard Scalp (ADX < 30)
                elif current_adx < 30:
                    if (current_pos > 0 and rsi_smooth > 75 and stoch_k > 80) or \
                       (current_pos < 0 and rsi_smooth < 25 and stoch_k < 20):
                         signal_msg = f"EXIT_DYNAMIC_SCALP (RSI {rsi_smooth:.1f}, Stoch {stoch_k:.1f})"
                         side = 'sell' if current_pos > 0 else 'buy'
                         action = {'symbol': symbol, 'side': side, 'amount': abs(current_pos), 'price': current_price, 'reason': signal_msg, 'reduceOnly': True}

            # 5. STAGNATION EXIT (Capital Efficiency)
            # If trade is > 2.0 hours old and ROI is tiny, kill it.
            # EXCEPTION: If ADX > 50 (Super Trend), we hold.
            
            # TIME-BASED STOP (The "Show Me The Money" Rule)
            # If a trade is 15 mins old (3 candles) and ROI is negative, kill it.
            # Momentum trades should work immediately.
            if not action and current_pos != 0 and duration_hours > 0.25 and roi_pct < -0.003:
                 signal_msg = f"EXIT_TIME_STOP (No Momentum in 15m, ROI {roi_pct*100:.2f}%)"
                 side = 'sell' if current_pos > 0 else 'buy'
                 action = {'symbol': symbol, 'side': side, 'amount': abs(current_pos), 'price': current_price, 'reason': signal_msg, 'reduceOnly': True}

            if not action and current_pos != 0 and duration_hours > 2.0 and current_adx < 50:
                if -0.005 < roi_pct < 0.005:
                     signal_msg = f"EXIT_STAGNATION (Duration {duration_hours:.1f}h)"
                     side = 'sell' if current_pos > 0 else 'buy'
                     action = {'symbol': symbol, 'side': side, 'amount': abs(current_pos), 'price': current_price, 'reason': signal_msg, 'reduceOnly': True}

            if not action:
                # CALCULATE STOP PRICE (High Leverage = Tight Stops)
                # Initial: 1.5 ATR. Tighten to 0.8 ATR.
                prev_trail_stop = pos_data.get('trail_stop', 0.0)
                atr_stop_mult = 1.5 
                
                # AGGRESSIVE PROFIT LOCKING
                if roi_pct > 0.015: # > 1.5% Profit
                    atr_stop_mult = 0.5 # Super tight to bank the win
                elif roi_pct > 0.008: # > 0.8% Profit
                    atr_stop_mult = 0.8 # Tighten
                
                if current_pos > 0: # LONG
                    new_trail_stop = max_price - (current_atr * atr_stop_mult)
                    # Never move stop down
                    if prev_trail_stop > new_trail_stop:
                        new_trail_stop = prev_trail_stop
                    
                    # Move to Breakeven ASAP
                    if roi_pct > 0.005 and new_trail_stop < entry: # Changed entry_price to entry to match existing variable
                        new_trail_stop = entry * 1.001 # BE + Fees
                    
                    # Ratchet: Never lower the stop (unless it was 0)
                    if prev_trail_stop > 0:
                        trail_stop = max(new_trail_stop, prev_trail_stop)
                    else:
                        trail_stop = new_trail_stop
                        
                    if current_price < trail_stop:
                        signal_msg = f"EXIT_TRAIL_STOP (ROI {roi_pct*100:.1f}%)"
                        action = {'symbol': symbol, 'side': 'sell', 'amount': abs(current_pos), 'price': current_price, 'reason': signal_msg, 'reduceOnly': True}
                        
                elif current_pos < 0: # SHORT
                    new_trail_stop = min_price + (current_atr * atr_stop_mult)
                    
                    # PROFIT RATCHET
                    min_pnl_fees = entry * 0.003
                    if peak_pnl > (current_atr * 0.5) and peak_pnl > min_pnl_fees:
                        new_trail_stop = min(new_trail_stop, entry - min_pnl_fees)
                        
                    if peak_pnl > (current_atr * 1.0):
                        new_trail_stop = min(new_trail_stop, entry - (current_atr * 0.5))
                    
                    # Ratchet: Never raise the stop (unless it was 0)
                    if prev_trail_stop > 0:
                        trail_stop = min(new_trail_stop, prev_trail_stop)
                    else:
                        trail_stop = new_trail_stop

                    if current_price > trail_stop:
                        signal_msg = f"EXIT_TRAIL_STOP (ROI {roi_pct*100:.1f}%)"
                        action = {'symbol': symbol, 'side': 'buy', 'amount': abs(current_pos), 'price': current_price, 'reason': signal_msg, 'reduceOnly': True}

                
        # ENTRY LOGIC (STRICT TREND FOLLOWING ONLY)
        if current_pos == 0:
            target_dir = 0
            
            # GLOBAL FILTER: Don't trade if ADX is too low (No Trend)
            # Use CONFIRMED ADX (iloc[-2]) to avoid repainting
            confirmed_adx = inds.get('confirmed_adx', current_adx)
            adx_threshold = params.get('adx_threshold', 20)
            
            if confirmed_adx < adx_threshold:
                return {
                    'symbol': symbol, 'price': current_price, 'trend': current_trend, 'rsi': rsi_value, 'adx': current_adx,
                    'signal': f"WAIT (Low ADX < {adx_threshold})", 'position': current_pos, 'pnl': pos_data['pnl'], 'action': None, 'score': 0,
                    'max_price': max_price, 'min_price': min_price, 'trail_stop': trail_stop
                }

            # 1. VOLATILITY SQUEEZE BREAKOUT (The "Big Move" Catcher)
            # Use CONFIRMED TREND (iloc[-2])
            # OPTIMIZATION: Lower ADX threshold to 20 if Momentum is rising (Catch early moves)
            adx_min = 25
            if adx_slope > 0:
                adx_min = 20
                
            if confirmed_trend == 1: # Bullish
                # Check if we just broke out
                if bullish_bias and confirmed_adx > adx_min:
                    target_dir = 1
                    signal_msg = "ENTRY_TREND_FOLLOW_LONG"
                    score = 5.0
            
            elif confirmed_trend == -1: # Bearish
                if bearish_bias and confirmed_adx > adx_min:
                    target_dir = -1
                    signal_msg = "ENTRY_TREND_FOLLOW_SHORT"
                    score = 5.0
            # ... (rest of logic) ...

            # ... (skipping to Dynamic Position Sizing block) ...
            
            # DYNAMIC POSITION SIZING (Smart Margin)
            if target_dir != 0:
                # Boost Score with ADX
                score += (current_adx / 20.0) # Max +2.5
                
                # FUNDING RATE ADJUSTMENT (Smart Money Bias)
                # Funding > 0: Longs pay Shorts (Crowded Longs -> Bearish Bias)
                # Funding < 0: Shorts pay Longs (Crowded Shorts -> Bullish Bias)
                
                if target_dir == 1: # LONG
                    if funding_rate < 0: score += 1.0 # Shorts fueling the move
                    if funding_rate > 0.05: score -= 2.0 # Too crowded, danger of flush
                
                elif target_dir == -1: # SHORT
                    if funding_rate > 0: score += 1.0 # Longs fueling the move
                    if funding_rate < -0.05: score -= 2.0 # Too crowded, danger of squeeze

                # Dynamic Risk Sizing
                # Base Risk is now 1.0% (Config)
                # If Score > 10 (Super Setup), we go to 1.5%
                base_risk = RISK_PER_TRADE 
                
                if score > 10.0:
                    risk_pct = base_risk * 1.5
                else:
                    risk_pct = base_risk
                
                # Risk Amount
                risk_amt = usdt_balance * risk_pct
                
                # Stop Distance (Fixed 1.5 ATR for consistency)
                stop_dist = current_atr * 1.5
                
                # Quantity based on Risk
                qty_risk = risk_amt / stop_dist
                
                # Quantity based on Leverage Cap
                max_qty_lev = (usdt_balance * LEVERAGE_CAP) / current_price
                
                # Final Quantity
                final_qty = min(qty_risk, max_qty_lev)
                
                # Ensure minimum notional
                if (final_qty * current_price) < 6:
                    final_qty = 0
                
                if final_qty > 0:
                    side = 'buy' if target_dir == 1 else 'sell'
                    action = {'symbol': symbol, 'side': side, 'amount': final_qty, 'price': current_price, 'reason': signal_msg, 'score': score}
            


        
        # Log the decision
        log_strategy_decision(symbol, inds, signal_msg, score, action, global_sentiment)
        
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

from threading import Lock

_log_lock = Lock()

def log_strategy_decision(symbol, inds, signal, score, action, sentiment):
    """Logs detailed strategy analysis to a separate file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Format indicators
    rsi = f"{inds['rsi_value']:.1f}" # Changed from inds['rsi'] to inds['rsi_value'] to match existing code
    adx = f"{inds['current_adx']:.1f}" # Changed from inds['adx'] to inds['current_adx']
    trend = f"{inds['current_trend']}" # Changed from inds['trend'] to inds['current_trend']
    slow_trend = f"{inds['slow_trend']}"
    
    # Momentum
    # Calculate ADX Slope for logging (retained from original logic)
    prev_adx = inds.get('prev_adx', inds['current_adx']) # Fallback
    adx_slope_val = inds['current_adx'] - prev_adx
    adx_slope = f"{adx_slope_val:.2f}" # Changed from inds.get('adx_slope', 0.0) to calculated value
    
    vol_ratio = "N/A"
    if inds.get('vol_sma') and inds['vol_sma'] > 0:
        vol_ratio = f"{inds['current_vol'] / inds['vol_sma']:.2f}x" # Changed from inds['vol'] to inds['current_vol']
        
    log_entry = (
        f"[{timestamp}] {symbol} | Sentiment: {sentiment:.2f}\n"
        f"   Inds: Price={inds['current_price']:.4f}, RSI={rsi}, ADX={adx}, Trend={trend}, SlowTrend={slow_trend}\n"
        f"   Momentum: ADX Slope={adx_slope}, Vol={inds['current_vol']} (SMA={inds['vol_sma']})\n" # Changed from inds['vol'] to inds['current_vol']
    )
    
    if action:
        log_entry += f"   ⚡ ENTRY: {action['side'].upper()} | Score: {score:.2f} | Reason: {action['reason']}\n"
    else:
        log_entry += f"   ❌ NO ENTRY. Reason: {signal}\n"
        
    log_entry += "-" * 50 + "\n"
    
    try:
        with _log_lock:
            with open("logs/strategy_analysis.log", "a") as f:
                f.write(log_entry)
    except Exception as e:
        print(f"Log Error: {e}")

# Add this call at the end of analyze_symbol before returning
# (I will inject this into the main function in the next step, but defining the helper here)
