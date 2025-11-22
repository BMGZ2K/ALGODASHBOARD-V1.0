import json
import os
import time
from datetime import datetime
from .config import STATE_FILE, SESSION_FILE

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}

def save_state(state):
    try:
        temp_file = f"{STATE_FILE}.tmp"
        with open(temp_file, 'w') as f:
            json.dump(state, f)
        os.replace(temp_file, STATE_FILE)
    except Exception as e:
        print(f"State Save Error: {e}")

def init_session(exchange):
    initial_balance = 0.0
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
        initial_balance = 1000.0 # Fallback
        
    return initial_balance

def merge_state_positions(active_positions, saved_state):
    """
    Restores max_price/min_price from saved state to active positions.
    """
    saved_positions = saved_state.get('positions', {})
    for sym, pos in active_positions.items():
        if sym in saved_positions:
            saved_p = saved_positions[sym]
            if 'max_price' in saved_p:
                pos['max_price'] = saved_p['max_price']
            if 'min_price' in saved_p:
                pos['min_price'] = saved_p['min_price']
            if 'dca_count' in saved_p:
                pos['dca_count'] = saved_p['dca_count']
