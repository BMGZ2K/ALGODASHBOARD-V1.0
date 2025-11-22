import csv
import os
import time
from datetime import datetime
from .config import LOG_FILE

def log_trade(timestamp, symbol, side, amount, price, reason, status):
    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, mode='a', newline='') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(['timestamp', 'symbol', 'side', 'amount', 'price', 'reason', 'status'])
        writer.writerow([timestamp, symbol, side, amount, price, reason, status])

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
    
    # Ensure symbol is uppercase to match CCXT keys
    symbol = symbol.upper()
    
    while attempts < max_attempts and not executed:
        try:
            # Dynamic precision formatting using CCXT's robust method
            # This handles stepSize, tickSize, and precisionMode automatically
            try:
                qty_str = exchange.amount_to_precision(symbol, final_amount)
            except Exception as e:
                print(f"      ⚠️ CCXT Precision Error: {e}. Fallback to int.")
                qty_str = str(int(final_amount))

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
                
                # Check min amount (approx)
                if (final_amount * price) < 5.0:
                     print("      ❌ Amount too small after resize. Aborting.")
                     break
                
            elif "-2022" in err_msg or "reduceonly" in err_msg:
                # ReduceOnly failed (maybe position closed already?)
                print(f"      ⚠️ ReduceOnly Error: {err_msg}")
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
