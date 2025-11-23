import csv
import os
import time
from datetime import datetime
from .config import LOG_FILE, LEVERAGE_CAP

def log_trade(timestamp, symbol, side, amount, price, reason, status, pnl=0.0):
    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, mode='a', newline='') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(['timestamp', 'symbol', 'side', 'amount', 'price', 'reason', 'status', 'pnl'])
        writer.writerow([timestamp, symbol, side, amount, price, reason, status, pnl])

def execute_trade_safely(exchange, symbol, side, amount, price, params, current_margin, active_positions, blacklist, signal_msg):
    """
    Executes a trade with robust error handling, retries, and raw API calls.
    Updates active_positions and returns the updated current_margin.
    """
    attempts = 0
    executed = False
    final_amount = amount
    leverage = LEVERAGE_CAP # Synced with Config
    max_attempts = 5
    realized_pnl = 0.0 # Track PnL for this trade
    
    # Ensure symbol is uppercase to match CCXT keys
    symbol = symbol.upper()
    last_error = "Unknown Error" # Initialize to prevent scope error
    
    while attempts < max_attempts and not executed:
        try:
            # Dynamic Minimum Amount & Notional Check
            try:
                market = exchange.market(symbol)
                min_amount = market['limits']['amount']['min']
                
                # Check Notional Value (Price * Amount)
                # Binance usually requires > $5. We use $6 for safety.
                notional_value = final_amount * price
                
                # Apply to Entries AND Partial TPs. 
                # Stop Losses (reduceOnly but not is_tp) should always execute to protect capital.
                if notional_value < 6.0:
                    if not params.get('reduceOnly', False):
                         # ENTRY: Bump to min or abort
                         min_notional_amount = 6.0 / price
                         if min_notional_amount > (final_amount * 3.0):
                             print(f"      ❌ Min Notional ($6) > 3x Risk Size (${notional_value:.2f}). Aborting.")
                             last_error = "Min Notional Exceeds Risk"
                             break
                         print(f"      ⚠️ Notional (${notional_value:.2f}) < $6. Adjusting amount to {min_notional_amount:.4f}")
                         final_amount = min_notional_amount
                    
                    elif params.get('is_tp', False):
                        # PARTIAL TP: Upgrade to Full Close
                        print(f"      ⚠️ Partial TP Notional (${notional_value:.2f}) < $6. Upgrading to FULL CLOSE.")
                        if symbol in active_positions:
                            final_amount = abs(active_positions[symbol]['amt'])
                        else:
                            # Fallback if we can't find pos (shouldn't happen)
                            min_notional_amount = 6.0 / price
                            final_amount = min_notional_amount

                if final_amount < min_amount:
                    if params.get('is_tp', False):
                        # If Partial TP is too small, close the ENTIRE position to secure gains
                        # Instead of failing, we upgrade to Full Close
                        print(f"      ⚠️ Partial TP ({final_amount}) < Min ({min_amount}). Upgrading to FULL CLOSE.")
                        # We need to find the full position size. 
                        # Since 'amount' passed to this function was already calculated as half, 
                        # we can try to infer or just use the min_amount if it covers the rest, 
                        # but safer is to check active_positions if available.
                        if symbol in active_positions:
                            final_amount = abs(active_positions[symbol]['amt'])
                        else:
                            final_amount = min_amount # Fallback
                    else:
                        # For entries, just bump to min if close enough, or abort?
                        # Safety: If min amount is > 3x our calculated risk size, ABORT.
                        if min_amount > (final_amount * 3.0):
                             print(f"      ❌ Min Amount ({min_amount}) > 3x Risk Size ({final_amount}). Aborting to protect risk.")
                             last_error = "Min Amount Exceeds Risk Tolerance"
                             break
                        
                        print(f"      ⚠️ Amount ({final_amount}) < Min ({min_amount}). Adjusting to Min.")
                        final_amount = min_amount
            except Exception as e:
                print(f"      ⚠️ Min Amount/Notional Check Error: {e}")

            # Dynamic precision formatting using CCXT's robust method
            # This handles stepSize, tickSize, and precisionMode automatically
            try:
                qty_str = exchange.amount_to_precision(symbol, final_amount)
            except Exception as e:
                print(f"      ⚠️ CCXT Precision Error: {e}. Attempting to reload markets...")
                try:
                    exchange.load_markets(reload=True)
                    qty_str = exchange.amount_to_precision(symbol, final_amount)
                except Exception as e2:
                     print(f"      ❌ Precision Failed: {e2}. Aborting trade to avoid invalid order.")
                     last_error = f"Precision Failed: {e2}"
                     break

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
            
            # Update active_positions immediately & Calculate PnL
            if params.get('reduceOnly', False):
                # Closing Position
                if symbol in active_positions:
                    # Calculate Realized PnL
                    entry_price = active_positions[symbol]['entry']
                    pos_amt = active_positions[symbol]['amt']
                    
                    # If we were Long (pos_amt > 0), we are Selling. PnL = (Exit - Entry) * Qty
                    # If we were Short (pos_amt < 0), we are Buying. PnL = (Entry - Exit) * Qty
                    
                    # Dynamic Fee Retrieval (Strict API)
                    try:
                        # Attempt to fetch exact fee rate for this symbol/user tier
                        # This is the most mathematically correct way
                        fee_data = exchange.fetch_trading_fee(symbol)
                        fee_rate = fee_data.get('taker', fee_data.get('fee', 0.0))
                        if fee_rate == 0.0:
                            # Fallback to market definition if fetchTradingFee returns 0 or fails
                            market_info = exchange.market(symbol)
                            fee_rate = market_info.get('taker', market_info.get('fee', 0.0))
                            
                        if fee_rate == 0.0:
                             # Final check on exchange properties (sometimes global)
                             fee_rate = exchange.fees['trading']['taker']
                    except Exception as e:
                        print(f"      ⚠️ Fee Fetch Error: {e}. Using Market Default.")
                        try:
                            market_info = exchange.market(symbol)
                            fee_rate = market_info.get('taker', 0.0005) # Last resort, but try to avoid
                        except:
                            fee_rate = 0.0005 # Absolute fallback if API is dead
                            
                    entry_fee = (entry_price * final_amount) * fee_rate
                    exit_fee = (price * final_amount) * fee_rate
                    total_fees = entry_fee + exit_fee

                    if pos_amt > 0: # Long Close
                        gross_pnl = (price - entry_price) * final_amount
                        remaining = pos_amt - final_amount
                    else: # Short Close
                        gross_pnl = (entry_price - price) * final_amount
                        remaining = abs(pos_amt) - final_amount
                    
                    realized_pnl = gross_pnl - total_fees
                    
                    # Update or Delete Position
                    # If remaining is tiny (dust), treat as closed
                    if remaining < (final_amount * 0.01) or remaining < 0.0001:
                        del active_positions[symbol]
                        print(f"      ✅ Position Closed Fully.")
                    else:
                        # Partial Close - Update Amount
                        new_amt = remaining if pos_amt > 0 else -remaining
                        active_positions[symbol]['amt'] = new_amt
                        print(f"      ℹ️  Partial Close. Remaining: {new_amt}")
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
                    active_positions[symbol] = {'amt': amt_signed, 'entry': price, 'pnl': 0.0, 'entry_time': datetime.now().isoformat(), 'dca_count': 0, 'tp_count': 0}
            
            # Handle Partial Take Profit State Update
            if params.get('is_tp', False) and symbol in active_positions:
                 active_positions[symbol]['tp_count'] = active_positions[symbol].get('tp_count', 0) + 1
                 print(f"      💰 Partial TP Executed. Count: {active_positions[symbol]['tp_count']}")
            
            # Log Trade with PnL
            log_trade(datetime.now().isoformat(), symbol, side, final_amount, price, signal_msg, "FILLED", realized_pnl)
            print(f"      ✅ FILLED: {order['orderId']} | PnL: ${realized_pnl:.2f}")

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
                
                # Check min amount (approx)
                if (final_amount * price) < 5.0:
                     print("      ❌ Amount too small after resize. Aborting.")
                     break
                
            elif "-2022" in err_msg or "reduceonly" in err_msg:
                print(f"      ⚠️ ReduceOnly Error: {err_msg}. Attempting to sync and recover...")
                try:
                    # 1. Cancel Open Orders (might be locking the position)
                    try:
                        exchange.cancel_all_orders(symbol)
                    except: pass # Ignore if no orders
                    time.sleep(0.5)
                    
                    # 2. Fetch Fresh Position
                    # Use unified fetch_positions
                    positions = exchange.fetch_positions([symbol]) if exchange.has['fetchPositions'] else []
                    
                    # Fallback if empty or not supported
                    if not positions:
                         positions = exchange.fetch_positions()
                    
                    target_pos = None
                    for p in positions:
                        if p['symbol'] == symbol:
                            target_pos = p
                            break
                    
                    if target_pos:
                        fresh_amt = float(target_pos['contracts']) if 'contracts' in target_pos else float(target_pos['info']['positionAmt'])
                        fresh_amt = abs(fresh_amt)
                        
                        if fresh_amt == 0:
                            print(f"      ✅ Position already closed on exchange. Marking as executed.")
                            executed = True
                            if symbol in active_positions: del active_positions[symbol]
                            break
                        elif fresh_amt < final_amount:
                             print(f"      ⚠️ Position size ({fresh_amt}) < Order ({final_amount}). Adjusting to full close.")
                             final_amount = fresh_amt
                             # Re-calculate precision
                             qty_str = exchange.amount_to_precision(symbol, final_amount)
                             req_params['quantity'] = qty_str
                        else:
                             print(f"      ⚠️ Position exists ({fresh_amt}). Retrying close...")
                    else:
                         # No position found
                         print(f"      ✅ No position found on exchange. Marking as executed.")
                         executed = True
                         if symbol in active_positions: del active_positions[symbol]
                         break
                         
                except Exception as recovery_e:
                    print(f"      ❌ Recovery Failed: {recovery_e}")
                
                attempts += 1
                time.sleep(0.5 * (attempts + 1))

            elif "-1111" in err_msg or "precision" in err_msg:
                print(f"      ⚠️ Precision Error from Exchange. Reloading markets...")
                exchange.load_markets(reload=True)
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
        log_trade(datetime.now().isoformat(), symbol, side, amount, price, signal_msg, f"FAILED: {last_error}", 0.0)
        
        # Auto-Blacklist on persistent unknown failures
        if attempts >= max_attempts:
             print(f"      🚫 Persistent Failures. Blacklisting {symbol} temporarily.")
             blacklist.add(symbol)

    return current_margin
