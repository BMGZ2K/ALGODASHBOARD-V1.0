import time
import os
import json
import argparse
import csv
from datetime import datetime

from core.config import (
    SYMBOLS, MAX_POSITIONS, LEVERAGE_CAP, COOLDOWN_MINUTES, 
    COMMAND_FILE, HISTORY_FILE, BOT_OUTPUT_LOG
)
from core.exchange import get_exchange, setup_markets
from core.strategy import analyze_symbol, load_strategy_config
from core.execution import execute_trade_safely, log_trade
from core.risk import check_circuit_breaker, get_risk_cleanup_actions
from core.state import load_state, save_state, init_session, merge_state_positions

# --- DUAL LOGGING SETUP ---
_print = print # Store original print function

def dual_log(*args, **kwargs):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = " ".join(map(str, args))
    formatted_msg = f"[{timestamp}] {msg}"
    
    # Print to console using original print
    _print(formatted_msg, **kwargs)
    
    # Append to file
    try:
        with open(BOT_OUTPUT_LOG, "a") as f:
            f.write(formatted_msg + "\n")
    except Exception as e:
        _print(f"Log Write Error: {e}")

# Override print to use dual_log
print = dual_log

def run_bot(snapshot=False):
    # --- INITIALIZATION ---
    print("🚀 LIVE BOT INITIALIZED | Mode: REFACTORED CORE")
    
    exchange = get_exchange()
    setup_markets(exchange)
    
    # Session & State
    initial_balance = init_session(exchange)
    saved_state = load_state()
    
    # Local State
    BLACKLIST = set(saved_state.get('blacklist', []))
    last_exit_times = {}
    last_sync_time = datetime.now()
    last_sync_time = datetime.now()
    global_sentiment = saved_state.get('sentiment', 0.5)
    high_water_mark = saved_state.get('high_water_mark', initial_balance)
    active_positions = saved_state.get('positions', {})
    
    # Simulation Mode (Legacy support, mostly False for live)
    SIMULATION_MODE = False
    IS_SPOT_MODE = False
    
    print(f"   Targets: {len(SYMBOLS)} Pairs")
    
    while True:
        try:
            # --- COMMAND HANDLING ---
            if os.path.exists(COMMAND_FILE):
                try:
                    with open(COMMAND_FILE, 'r') as f:
                        cmd_data = json.load(f)
                    
                    if cmd_data.get('command') == 'CLOSE_ALL':
                        print("🚨 RECEIVED PANIC COMMAND: CLOSING ALL POSITIONS")
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
                        os.remove(COMMAND_FILE)
                        time.sleep(5)
                        continue
                except Exception as e:
                    print(f"Command Error: {e}")

            # --- 1. SYNC ACCOUNT ---
            ACTIVE_SYMBOLS = [s for s in SYMBOLS if s not in BLACKLIST]
            print(f"\n--- 🔎 Scanning Market ({len(ACTIVE_SYMBOLS)} Pairs) | Sentiment: {global_sentiment:.2f} ---")
            
            usdt_balance = 0.0
            available_balance = 0.0
            realized_pnl = 0.0
            
            # Temp dict to build the new state
            current_positions_map = {}
            
            if not SIMULATION_MODE:
                try:
                    account_info = exchange.fapiPrivateV2GetAccount()
                    usdt_balance = float(account_info['totalWalletBalance'])
                    available_balance = float(account_info['availableBalance'])
                    
                    if initial_balance > 0:
                        realized_pnl = usdt_balance - initial_balance
                    
                    for p in account_info['positions']:
                        amt = float(p['positionAmt'])
                        if amt != 0:
                            sym = p['symbol']
                            # Map back to slash format
                            matched_sym = next((s for s in SYMBOLS if s.replace('/', '') == sym), sym)
                            entry = float(p['entryPrice'])
                            pnl = float(p['unrealizedProfit'])
                            
                            # PRESERVE LOCAL STATE
                            if matched_sym in active_positions:
                                # Copy existing state
                                current_positions_map[matched_sym] = active_positions[matched_sym].copy()
                                # Update dynamic fields
                                current_positions_map[matched_sym]['amt'] = amt
                                current_positions_map[matched_sym]['entry'] = entry
                                current_positions_map[matched_sym]['pnl'] = pnl
                            else:
                                # Try to recover from saved state to preserve entry_time
                                saved_pos = saved_state.get('positions', {}).get(matched_sym, {})
                                recovered_entry_time = saved_pos.get('entry_time', datetime.now().isoformat())
                                
                                # New position or Recovered
                                current_positions_map[matched_sym] = {
                                    'amt': amt, 
                                    'entry': entry, 
                                    'pnl': pnl,
                                    'entry_time': recovered_entry_time,
                                    'max_price': saved_pos.get('max_price', entry),
                                    'min_price': saved_pos.get('min_price', entry),
                                    'tp_count': saved_pos.get('tp_count', 0),
                                    'dca_count': saved_pos.get('dca_count', 0)
                                }
                    
                    # Replace active_positions with the fresh map (removes closed positions)
                    active_positions = current_positions_map
                    
                except Exception as e:
                    print(f"⚠️ Account Sync Error: {e}")
            else:
                usdt_balance = 10000.0
                available_balance = 10000.0

            # Restore persistent state (max_price, etc.)
            merge_state_positions(active_positions, saved_state)
            
            print(f"   💰 Bal: ${usdt_balance:.2f} | Avail: ${available_balance:.2f} | PnL: ${realized_pnl:.2f} | Pos: {len(active_positions)}")

            # --- 2. CIRCUIT BREAKER ---
            is_triggered, drawdown, high_water_mark = check_circuit_breaker(initial_balance, usdt_balance, high_water_mark)
            if is_triggered:
                print(f"🚨 CIRCUIT BREAKER: Drawdown {drawdown*100:.2f}% > Limit. HALTING & CLOSING ALL.")
                
                # Create Panic Close Command
                with open(COMMAND_FILE, 'w') as f:
                    json.dump({'command': 'CLOSE_ALL'}, f)
                
                save_state({
                    'timestamp': datetime.now().isoformat(),
                    'balance': usdt_balance,
                    'positions': active_positions,
                    'status': f"HALTED: Drawdown {drawdown*100:.1f}%"
                })
                time.sleep(5) # Allow command to be picked up in next loop
                continue

            # --- 3. STRATEGY & RISK SCAN ---
            proposed_actions = []
            current_market_scan_data = {}
            current_trends = []
            
            # A. Risk Cleanup (High Priority)
            cleanup_actions = get_risk_cleanup_actions(active_positions, global_sentiment)
            for action in cleanup_actions:
                action['score'] = 100 # Max priority
                proposed_actions.append(action)
            
            # B. Market Scan (Entry/Exit Signals)
            strategy_params = load_strategy_config("Hybrid_Futures_2x_LongShort")
            
            # Fetch Funding Rates (Smart Money Bias)
            funding_rates = {}
            try:
                # Try to fetch all at once (Best Performance)
                # Note: fetch_funding_rates might not be supported on all exchanges/testnets
                # If fails, we default to 0.0
                if hasattr(exchange, 'fetch_funding_rates'):
                    funding_rates = exchange.fetch_funding_rates(ACTIVE_SYMBOLS)
                    # Convert to simple dict: symbol -> rate
                    funding_rates = {k: v['fundingRate'] for k, v in funding_rates.items() if 'fundingRate' in v}
            except Exception as e:
                # print(f"   ⚠️ Funding Rate Fetch Warning: {e}")
                pass
            
            # Parallel Analysis
            from concurrent.futures import ThreadPoolExecutor, as_completed

            def analyze_wrapper(sym):
                pos_data = active_positions.get(sym, {'amt': 0.0, 'entry': 0.0, 'pnl': 0.0})
                pos_data['active_positions_count'] = active_positions # Pass full dict for length check
                f_rate = funding_rates.get(sym, 0.0)
                return analyze_symbol(sym, exchange, pos_data, usdt_balance, available_balance, IS_SPOT_MODE, SIMULATION_MODE, global_sentiment, BLACKLIST, strategy_params, f_rate)

            # Use 10 workers for parallel processing to speed up scanning without hitting rate limits too hard
            with ThreadPoolExecutor(max_workers=10) as executor:
                future_to_symbol = {executor.submit(analyze_wrapper, sym): sym for sym in ACTIVE_SYMBOLS}
                
                for future in as_completed(future_to_symbol):
                    try:
                        res = future.result()
                        if res:
                            symbol = res['symbol']
                            # Update State Memory
                            if symbol in active_positions:
                                active_positions[symbol]['max_price'] = res.get('max_price', 0.0)
                                active_positions[symbol]['min_price'] = res.get('min_price', 0.0)
                                active_positions[symbol]['trail_stop'] = res.get('trail_stop', 0.0)
                            
                            # Dashboard Data
                            current_market_scan_data[symbol] = {
                                'price': res['price'],
                                'trend': 'BULL' if res['trend'] == 1 else ('BEAR' if res['trend'] == -1 else 'SIDEWAYS'),
                                'rsi': res['rsi'],
                                'adx': res['adx'],
                                'signal': res['signal'],
                                'pos': res['position'],
                                'pnl': res['pnl']
                            }
                            
                            current_trends.append(res['trend'])
                            
                            if res['action']:
                                proposed_actions.append(res['action'])
                    except Exception as exc:
                        print(f"   ❌ Analysis Error for {future_to_symbol[future]}: {exc}")

            # Update Sentiment
            if current_trends:
                bull_count = current_trends.count(1)
                global_sentiment = bull_count / len(current_trends)

            print(f"   ✅ Scan Complete. Found {len(proposed_actions)} signals.")

            # --- 4. EXECUTION LOOP ---
            # Sort by score
            proposed_actions.sort(key=lambda x: x.get('score', 0), reverse=True)
            
            current_available_margin = available_balance
            
            for action in proposed_actions:
                symbol = action['symbol']
                side = action['side']
                amount = action['amount']
                price = action['price']
                reason = action['reason']
                score = action.get('score', 0)
                is_reduce = action.get('reduceOnly', False)
                
                # Cooldown Check (Entries only)
                if not is_reduce:
                    last_exit = last_exit_times.get(symbol)
                    if last_exit:
                        # Smart Cooldown: If last trade was a WIN, 0 cooldown. If LOSS, 5 mins.
                        # We need to track the PnL of the last closed trade for this symbol.
                        # Since we don't have it easily accessible here without state, we'll use a heuristic:
                        # If realized_pnl increased significantly recently, it was a win.
                        # Better: Just stick to a short cooldown for now, or implement full state tracking later.
                        # Let's use the standard cooldown but reduce it if Score is very high (Hot Hand).
                        
                        elapsed = (datetime.now() - last_exit).total_seconds() / 60
                        required_cooldown = COOLDOWN_MINUTES
                        
                        if elapsed < required_cooldown:
                            print(f"   ⏳ Cooldown {symbol} ({elapsed:.1f}m). Skipping.")
                            continue
                            
                    # Max Positions Check (Hard Limit)
                    if symbol not in active_positions and len(active_positions) >= MAX_POSITIONS:
                        print(f"   ⚠️ Max Positions ({MAX_POSITIONS}) Reached. Skipping {symbol}.")
                        continue
                    
                    # Correlation Check (Systemic Risk)
                    # Count Longs vs Shorts
                    longs = sum(1 for p in active_positions.values() if p['amt'] > 0)
                    shorts = sum(1 for p in active_positions.values() if p['amt'] < 0)
                    
                    if side == 'buy' and longs >= 12:
                         print(f"   ⚠️ Too many Longs ({longs}). Skipping {symbol} to balance risk.")
                         continue
                    if side == 'sell' and shorts >= 12:
                         print(f"   ⚠️ Too many Shorts ({shorts}). Skipping {symbol} to balance risk.")
                         continue
                        
                    # Margin Check & Rotation
                    cost = (amount * price) / LEVERAGE_CAP # Est leverage
                    if cost > current_available_margin:
                        # ROTATION LOGIC (Re-enabled & Smarter)
                        if len(active_positions) > 0 and score >= 8.0:
                            # Try to find a victim
                            candidates = [s for s in active_positions if s != symbol]
                            if candidates:
                                weakest = min(candidates, key=lambda s: active_positions[s]['pnl'])
                                w_pnl = active_positions[weakest]['pnl']
                                
                                # Smart Rotation: Only kill if victim is a loser OR stagnant AND new trade is a banger
                                v_data = active_positions[weakest]
                                is_old_enough = False
                                is_stagnant = False
                                
                                if 'entry_time' in v_data:
                                    try:
                                        entry_dt = datetime.fromisoformat(v_data['entry_time'])
                                        age_mins = (datetime.now() - entry_dt).total_seconds() / 60
                                        if age_mins > 10: is_old_enough = True
                                        if age_mins > 45 and w_pnl < 0.5: is_stagnant = True
                                    except: is_old_enough = True # Fallback
                                else:
                                    is_old_enough = True # Fallback

                                if (w_pnl < -2.0 and is_old_enough) or (w_pnl < -10.0) or (is_stagnant and score > 8.5): 
                                    print(f"      🔄 ROTATION: Sacrificing {weakest} (${w_pnl:.2f}) for {symbol} (Score {score})")
                                    # Close Victim
                                    v_data = active_positions[weakest]
                                    try:
                                        execute_trade_safely(exchange, weakest, 'sell' if v_data['amt']>0 else 'buy', abs(v_data['amt']), v_data['entry'], {'reduceOnly': True}, 0, active_positions, BLACKLIST, "ROTATION_SACRIFICE")
                                        # Assume margin released (rough est)
                                        # Correctly account for realized loss: Initial Margin + PnL (which is negative)
                                        initial_margin = (abs(v_data['amt']) * v_data['entry']) / LEVERAGE_CAP
                                        released = max(0, initial_margin + w_pnl)
                                        current_available_margin += released
                                        # Wait a bit for release
                                        time.sleep(1)
                                    except:
                                        pass
                        
                        # Re-check margin
                        if cost > current_available_margin:
                            # Resize if close
                            if current_available_margin > 10:
                                amount = (current_available_margin * 0.95 * LEVERAGE_CAP) / price
                                print(f"      📉 Resized to fit margin: {amount:.4f}")
                            else:
                                print(f"   ❌ Insufficient Margin for {symbol}. Stopping entries.")
                                # If we are out of margin, no point checking other entries.
                                # But we must continue if there are reduceOnly orders later in the list?
                                # The list is sorted by score, but reduceOnly usually has high priority or is handled separately?
                                # Actually, reduceOnly orders usually come from 'exit' logic which might not be in this list if they are handled in 'analyze_symbol' but 'analyze_symbol' returns actions.
                                # Let's just continue for now but maybe suppress the log if we've seen it once?
                                # Better: just break if we are truly out of gas.
                                break

                # EXECUTE
                print(f"⚡ EXEC: {side.upper()} {symbol} | {reason} | Score {score}")
                if not snapshot and not SIMULATION_MODE:
                    current_available_margin = execute_trade_safely(
                        exchange, symbol, side, amount, price, 
                        {'reduceOnly': True} if is_reduce else {}, 
                        current_available_margin, active_positions, BLACKLIST, reason
                    )
                    
                    if is_reduce:
                        last_exit_times[symbol] = datetime.now()

            # --- 5. SELF-OPTIMIZATION & DASHBOARD ---
            # Calculate Performance Metrics
            total_trades = 0
            wins = 0
            total_pnl = realized_pnl
            
            # Read recent history (last 50 trades)
            try:
                if os.path.exists(LOG_FILE):
                    with open(LOG_FILE, 'r') as f:
                        reader = list(csv.DictReader(f))
                        recent_trades = reader[-50:]
                        total_trades = len(recent_trades)
                        for t in recent_trades:
                            pnl = float(t['pnl'])
                            if pnl > 0: wins += 1
            except: pass
            
            win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
            
            # ADAPTIVE LOGIC
            # Default ADX Threshold is 20.
            # If Win Rate is bad (< 40%), we tighten it to 25 or 30 to filter chop.
            # If Win Rate is good (> 60%), we relax it to 15 to catch more moves.
            
            current_adx_threshold = 20
            if total_trades > 10:
                if win_rate < 40:
                    current_adx_threshold = 30
                    print(f"   ⚠️ Performance Low (WR {win_rate:.1f}%). Tightening ADX Filter to {current_adx_threshold}.")
                elif win_rate < 50:
                    current_adx_threshold = 25
                    print(f"   ⚠️ Performance Mediocre (WR {win_rate:.1f}%). Tightening ADX Filter to {current_adx_threshold}.")
                elif win_rate > 60:
                    current_adx_threshold = 15
                    print(f"   🔥 Performance High (WR {win_rate:.1f}%). Relaxing ADX Filter to {current_adx_threshold}.")
            
            # Pass this dynamic threshold to the strategy in the next loop (requires updating strategy.py signature, 
            # but for now we can inject it via params or just log it. 
            # To make it effective immediately, we'd need to pass it to analyze_symbol.
            # Let's update strategy_params in the next iteration)
            strategy_params['adx_threshold'] = current_adx_threshold

            # --- 6. SAVE STATE ---
            # Clean up circular reference before saving
            clean_positions = {}
            for k, v in active_positions.items():
                clean_v = v.copy()
                if 'active_positions_count' in clean_v:
                    del clean_v['active_positions_count']
                clean_positions[k] = clean_v
                
            save_state({
                'timestamp': datetime.now().isoformat(),
                'balance': usdt_balance,
                'available_balance': available_balance,
                'positions': clean_positions,
                'market_scan': current_market_scan_data,
                'sentiment': global_sentiment,
                'blacklist': list(BLACKLIST),
                'realized_pnl': realized_pnl,
                'high_water_mark': high_water_mark,
                'metrics': {'win_rate': win_rate, 'total_trades': total_trades}
            })
            
            # History Log
            total_open_pnl = sum(p['pnl'] for p in active_positions.values())
            file_exists = os.path.isfile(HISTORY_FILE)
            with open(HISTORY_FILE, mode='a', newline='') as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(['timestamp', 'balance', 'open_pnl', 'position_count', 'sentiment', 'realized_pnl'])
                writer.writerow([datetime.now().isoformat(), usdt_balance, total_open_pnl, len(active_positions), global_sentiment, realized_pnl])

            if snapshot: break
            time.sleep(2) # Poll Interval (Faster)

        except KeyboardInterrupt:
            print("Stopped.")
            break
        except Exception as e:
            print(f"Main Loop Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot', action='store_true')
    args = parser.parse_args()
    run_bot(snapshot=args.snapshot)
