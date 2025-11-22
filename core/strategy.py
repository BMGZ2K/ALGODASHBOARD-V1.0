import pandas as pd
import os
import ast
from datetime import datetime
from .indicators import calculate_indicators
from .config import LEVERAGE_CAP, DEFAULT_STRATEGY_CONFIG

def load_strategy_config(strategy_name):
    path = f"config/strategies/{strategy_name}_config.txt"
    if not os.path.exists(path):
        return DEFAULT_STRATEGY_CONFIG
    with open(path, 'r') as f:
        return ast.literal_eval(f.read())

def analyze_symbol(symbol, exchange, pos_data, usdt_balance, available_balance, is_spot, is_sim, global_sentiment, blacklist, params):
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
        current_adx = inds['current_adx']
        current_trend = inds['current_trend']
        slow_trend = inds['slow_trend']
        lower_bb = inds['lower_bb']
        upper_bb = inds['upper_bb']
        current_width = inds['current_width']
        width_threshold = inds['width_threshold']
        current_vol = inds['current_vol']
        vol_sma = inds['vol_sma']
        stoch_k = inds['stoch_k']
        stoch_d = inds['stoch_d']
        prev_stoch_k = inds['prev_stoch_k']
        prev_stoch_d = inds['prev_stoch_d']
        donchian_high = inds['donchian_high']
        donchian_low = inds['donchian_low']

        # Strategy Logic
        signal_msg = "WAIT"
        action = None
        score = 0
        trail_stop = 0.0 # For visualization
        current_pos = pos_data['amt']
        
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

        # ADX Slope Calculation (Trend Strength Momentum)
        prev_adx = inds.get('prev_adx', current_adx) # Fallback if not available
        adx_slope = current_adx - prev_adx

        # EXIT LOGIC
        if current_pos != 0:
            atr_stop_mult = 2.0
            entry = pos_data['entry']
            pnl_per_unit = (current_price - entry) if current_pos > 0 else (entry - current_price)
            roi_pct = pnl_per_unit / entry if entry > 0 else 0
            
            # 1. Volume Climax Exit (Panic/Euphoria Catcher)
            if current_vol > (vol_sma * 3.0):
                if current_pos > 0 and rsi_value > 80:
                    signal_msg = "EXIT_CLIMAX_PUMP"
                    action = {'symbol': symbol, 'side': 'sell', 'amount': abs(current_pos), 'price': current_price, 'reason': signal_msg, 'reduceOnly': True}
                elif current_pos < 0 and rsi_value < 20:
                    signal_msg = "EXIT_CLIMAX_DUMP"
                    action = {'symbol': symbol, 'side': 'buy', 'amount': abs(current_pos), 'price': current_price, 'reason': signal_msg, 'reduceOnly': True}

            # 2. Hard Take Profit (3.5x ATR) - Bank Big Wins
            if not action and pnl_per_unit > (current_atr * 3.5):
                if current_adx < 50: # Only cap profit if trend isn't insane
                    signal_msg = "EXIT_TP_HARD"
                    side = 'sell' if current_pos > 0 else 'buy'
                    action = {'symbol': symbol, 'side': side, 'amount': abs(current_pos), 'price': current_price, 'reason': signal_msg, 'reduceOnly': True}
                else:
                    pass # Let it run!
            
            # 3. Smart Trailing Stop (Chandelier + ATR Ratchet)
            elif not action:
                # DYNAMIC MULTIPLIER based on Profit Depth
                peak_pnl = (max_price - entry) if current_pos > 0 else (entry - min_price)
                
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

                # STAGNATION EXIT (Time-Based)
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
                if not action and roi_pct < -0.02 and roi_pct > -0.06: # Down 2-6%
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
                            
                            action = {'symbol': symbol, 'side': side, 'amount': add_amt, 'price': current_price, 'reason': signal_msg, 'score': 8.5, 'is_dca': True}

                if not action:
                    # CALCULATE STOP PRICE (Chandelier Logic + ATR Ratchet)
                    if current_pos > 0: # LONG
                        trail_stop = max_price - (current_atr * atr_stop_mult)
                        
                        # ATR-BASED PROFIT RATCHET (Volatility Adjusted)
                        # Level 1: Secure Breakeven + Fees once > 1 ATR profit
                        if peak_pnl > (current_atr * 1.0):
                            trail_stop = max(trail_stop, entry + (current_atr * 0.1))
                        
                        # Level 2: Secure 0.5 ATR profit once > 2 ATR profit
                        if peak_pnl > (current_atr * 2.0):
                            trail_stop = max(trail_stop, entry + (current_atr * 0.5))
                            
                        # Level 3: Secure 1.5 ATR profit once > 3 ATR profit
                        if peak_pnl > (current_atr * 3.0):
                            trail_stop = max(trail_stop, entry + (current_atr * 1.5))
                        
                        # CHOPPY MARKET SCALP
                        if current_adx < 25 and roi_pct > 0.015:
                             signal_msg = f"EXIT_CHOP_SCALP (ROI {roi_pct*100:.1f}%)"
                             action = {'symbol': symbol, 'side': 'sell', 'amount': abs(current_pos), 'price': current_price, 'reason': signal_msg, 'reduceOnly': True}

                        if current_price < trail_stop:
                            signal_msg = f"EXIT_TRAIL_STOP (ROI {roi_pct*100:.1f}%)"
                            action = {'symbol': symbol, 'side': 'sell', 'amount': abs(current_pos), 'price': current_price, 'reason': signal_msg, 'reduceOnly': True}
                            
                    elif current_pos < 0: # SHORT
                        trail_stop = min_price + (current_atr * atr_stop_mult)
                        
                        # ATR-BASED PROFIT RATCHET
                        if peak_pnl > (current_atr * 1.0):
                            trail_stop = min(trail_stop, entry - (current_atr * 0.1))
                            
                        if peak_pnl > (current_atr * 2.0):
                            trail_stop = min(trail_stop, entry - (current_atr * 0.5))
                            
                        if peak_pnl > (current_atr * 3.0):
                            trail_stop = min(trail_stop, entry - (current_atr * 1.5))
                        
                        # CHOPPY MARKET SCALP
                        if current_adx < 25 and roi_pct > 0.015:
                             signal_msg = f"EXIT_CHOP_SCALP (ROI {roi_pct*100:.1f}%)"
                             action = {'symbol': symbol, 'side': 'buy', 'amount': abs(current_pos), 'price': current_price, 'reason': signal_msg, 'reduceOnly': True}

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
            
            # Regime Detection
            if current_adx > 20: # Trend (Relaxed to 20)
                # Volume Filter
                if current_vol > (vol_sma * 0.8):
                    # 1. DONCHIAN BREAKOUT
                    if current_price > donchian_high and current_vol > (vol_sma * 1.5) and slow_trend == 1:
                        target_dir = 1
                        signal_msg = "LONG_BREAKOUT_DONCHIAN"
                        score = 9.5
                    elif current_price < donchian_low and current_vol > (vol_sma * 1.5) and slow_trend == -1:
                        target_dir = -1
                        signal_msg = "SHORT_BREAKOUT_DONCHIAN"
                        score = 9.5
                    
                    # 2. STANDARD PULLBACK ENTRY
                    elif current_trend == slow_trend:
                        # Require Rising Momentum for Trend Entry
                        if adx_slope > -0.5: # Allow slight dip but avoid crashing momentum
                            if current_trend == 1 and rsi_value < 55:
                                target_dir = 1
                                signal_msg = "LONG_TREND_ALIGNED"
                                score = 10
                            elif current_trend == -1 and rsi_value > 45:
                                target_dir = -1
                                signal_msg = "SHORT_TREND_ALIGNED"
                                score = 10
                    
                    # 3. TREND CONTINUATION (Extreme Sentiment)
                    elif current_adx > 25 and adx_slope > 0: # Strict Momentum Check
                        # Extreme Bear
                        if global_sentiment < 0.2 and current_trend == -1 and slow_trend == -1:
                            if rsi_value > 40 and rsi_value < 60: 
                                target_dir = -1
                                signal_msg = "SHORT_TREND_CONTINUATION"
                                score = 8.5
                        
                        # Extreme Bull
                        elif global_sentiment > 0.8 and current_trend == 1 and slow_trend == 1:
                            if rsi_value < 60 and rsi_value > 40:
                                target_dir = 1
                                signal_msg = "LONG_TREND_CONTINUATION"
                                score = 8.5

            else: # Range / Squeeze
                # 1. VOLATILITY SQUEEZE BREAKOUT
                if current_width < width_threshold: 
                    if current_price > upper_bb and current_vol > vol_sma and slow_trend == 1:
                        target_dir = 1
                        signal_msg = "LONG_SQUEEZE_BREAKOUT"
                        score = 9
                    elif current_price < lower_bb and current_vol > vol_sma and slow_trend == -1:
                        target_dir = -1
                        signal_msg = "SHORT_SQUEEZE_BREAKOUT"
                        score = 9
            
            # DYNAMIC POSITION SIZING (Smart Margin)
            if target_dir != 0:
                # Boost Score with ADX
                score += (current_adx / 10.0)
                
                # Boost Score with Volatility
                volatility_pct = (current_atr / current_price) * 100
                score += volatility_pct
                
                # Dynamic Risk Sizing
                if score >= 9.0:
                    risk_pct = 0.05 # 5% Risk for A+ Setups
                elif score >= 8.0:
                    risk_pct = 0.03 # 3% Risk for Strong Setups
                else:
                    risk_pct = 0.0 # Skip anything below Score 8
                
                # Risk Amount
                risk_amt = usdt_balance * risk_pct
                
                # Stop Distance (1.5 ATR)
                stop_dist = current_atr * 1.5
                if stop_dist == 0: stop_dist = current_price * 0.01
                
                # Quantity based on Risk
                qty_risk = risk_amt / stop_dist
                
                # Quantity based on Leverage Cap
                max_qty_lev = (usdt_balance * LEVERAGE_CAP) / current_price
                
                # Quantity based on Available Margin
                max_qty_margin = (available_balance * 0.95 * LEVERAGE_CAP) / current_price

                # MAX NOTIONAL CAP
                total_buying_power = usdt_balance * LEVERAGE_CAP
                max_notional_per_trade = total_buying_power * 0.15 
                max_qty_notional = max_notional_per_trade / current_price
                
                # Final Quantity
                final_qty = min(qty_risk, max_qty_lev, max_qty_margin, max_qty_notional)
                
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

def log_strategy_decision(symbol, inds, signal_msg, score, action, global_sentiment):
    """Logs detailed strategy analysis to a separate file."""
    log_file = "logs/strategy_analysis.log"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open(log_file, "a") as f:
        f.write(f"[{timestamp}] {symbol} | Sentiment: {global_sentiment:.2f}\n")
        f.write(f"  Inds: Price={inds['current_price']:.4f}, RSI={inds['rsi_value']:.1f}, ADX={inds['current_adx']:.1f}, Trend={inds['current_trend']}, SlowTrend={inds['slow_trend']}\n")
        
        # Calculate ADX Slope for logging
        prev_adx = inds.get('prev_adx', inds['current_adx']) # Fallback
        adx_slope = inds['current_adx'] - prev_adx
        f.write(f"  Momentum: ADX Slope={adx_slope:.2f}, Vol={inds['current_vol']:.0f} (SMA={inds['vol_sma']:.0f})\n")

        if action:
            f.write(f"  ✅ ACTION: {action['side'].upper()} | Reason: {signal_msg} | Score: {score:.2f}\n")
        else:
            f.write(f"  ❌ NO ENTRY. Reason: {signal_msg}\n")
            # Add specific rejection reasons based on logic
            if inds['current_adx'] <= 20: f.write("     - ADX too low (<20) for Trend Entry\n")
            if inds['current_trend'] != inds['slow_trend']: f.write("     - Trend Mismatch (Fast vs Slow)\n")
            if adx_slope <= -0.5: f.write("     - ADX Slope Negative (Momentum Fading)\n")
            
        f.write("-" * 50 + "\n")

# Add this call at the end of analyze_symbol before returning
# (I will inject this into the main function in the next step, but defining the helper here)
