import time
import os
import json
import argparse
import csv
from datetime import datetime

from core.config import (
    SYMBOLS, MAX_POSITIONS, LEVERAGE_CAP, COOLDOWN_MINUTES, 
    COMMAND_FILE, HISTORY_FILE
)
from core.exchange import get_exchange, setup_markets
from core.strategy import analyze_symbol, load_strategy_config
from core.execution import execute_trade_safely, log_trade
from core.risk import check_circuit_breaker, get_risk_cleanup_actions
from core.state import load_state, save_state, init_session, merge_state_positions

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
    global_sentiment = saved_state.get('sentiment', 0.5)
    
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
            active_positions = {}
            
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
                            active_positions[matched_sym] = {'amt': amt, 'entry': entry, 'pnl': pnl}
                except Exception as e:
                    print(f"⚠️ Account Sync Error: {e}")
            else:
                usdt_balance = 10000.0
                available_balance = 10000.0

            # Restore persistent state (max_price, etc.)
            merge_state_positions(active_positions, saved_state)
            
            print(f"   💰 Bal: ${usdt_balance:.2f} | Avail: ${available_balance:.2f} | PnL: ${realized_pnl:.2f} | Pos: {len(active_positions)}")

            # --- 2. CIRCUIT BREAKER ---
            triggered, drawdown = check_circuit_breaker(initial_balance, usdt_balance)
            if triggered:
                print(f"🚨 CIRCUIT BREAKER: Drawdown {drawdown*100:.2f}% > Limit. HALTING.")
                save_state({
                    'timestamp': datetime.now().isoformat(),
                    'balance': usdt_balance,
                    'positions': active_positions,
                    'status': f"HALTED: Drawdown {drawdown*100:.1f}%"
                })
                time.sleep(60)
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
            
            # Parallel Analysis
            from concurrent.futures import ThreadPoolExecutor, as_completed

            def analyze_wrapper(sym):
                pos_data = active_positions.get(sym, {'amt': 0.0, 'entry': 0.0, 'pnl': 0.0})
                return analyze_symbol(sym, exchange, pos_data, usdt_balance, available_balance, IS_SPOT_MODE, SIMULATION_MODE, global_sentiment, BLACKLIST, strategy_params)

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
                        elapsed = (datetime.now() - last_exit).total_seconds() / 60
                        if elapsed < COOLDOWN_MINUTES:
                            print(f"   ⏳ Cooldown {symbol} ({elapsed:.1f}m). Skipping.")
                            continue
                            
                    # Max Positions Check
                    if symbol not in active_positions and len(active_positions) >= MAX_POSITIONS:
                        print(f"   ⚠️ Max Positions Reached. Skipping {symbol}.")
                        continue
                        
                    # Margin Check & Rotation
                    cost = (amount * price) / 5 # Est leverage 5
                    if cost > current_available_margin:
                        # ROTATION LOGIC
                        if len(active_positions) > 0 and score >= 8:
                            # Try to find a victim
                            candidates = [s for s in active_positions if s != symbol]
                            if candidates:
                                weakest = min(candidates, key=lambda s: active_positions[s]['pnl'])
                                w_pnl = active_positions[weakest]['pnl']
                                
                                if (score >= 9.5 and w_pnl < 0) or (score >= 9.8 and w_pnl < 2):
                                    print(f"      🔄 ROTATION: Sacrificing {weakest} (${w_pnl:.2f}) for {symbol} (Score {score})")
                                    # Close Victim
                                    v_data = active_positions[weakest]
                                    try:
                                        execute_trade_safely(exchange, weakest, 'sell' if v_data['amt']>0 else 'buy', abs(v_data['amt']), v_data['entry'], {'reduceOnly': True}, 0, active_positions, BLACKLIST, "ROTATION_SACRIFICE")
                                        # Assume margin released (rough est)
                                        released = (abs(v_data['amt']) * v_data['entry']) / 5
                                        current_available_margin += released
                                    except:
                                        pass
                        
                        # Re-check margin
                        if cost > current_available_margin:
                            # Resize if close
                            if current_available_margin > 10:
                                amount = (current_available_margin * 0.95 * 5) / price
                                print(f"      📉 Resized to fit margin: {amount:.4f}")
                            else:
                                print(f"   ❌ Insufficient Margin for {symbol}. Skipping.")
                                continue

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

            # --- 5. SAVE STATE ---
            save_state({
                'timestamp': datetime.now().isoformat(),
                'balance': usdt_balance,
                'available_balance': available_balance,
                'positions': active_positions,
                'market_scan': current_market_scan_data,
                'sentiment': global_sentiment,
                'blacklist': list(BLACKLIST),
                'realized_pnl': realized_pnl
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
            time.sleep(5) # Poll Interval

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
