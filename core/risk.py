from datetime import datetime
from .config import CIRCUIT_BREAKER_DRAWDOWN

def check_circuit_breaker(initial_balance, current_balance):
    """
    Checks if drawdown exceeds the limit.
    Returns (is_triggered, drawdown_pct)
    """
    if initial_balance <= 0: return False, 0.0
    drawdown_pct = (initial_balance - current_balance) / initial_balance
    return drawdown_pct > CIRCUIT_BREAKER_DRAWDOWN, drawdown_pct

def get_risk_cleanup_actions(active_positions, global_sentiment):
    """
    Scans active positions for Stale, Zombie, Toxic, or Wrong-Way trades.
    Returns a list of actions (dicts) to close these positions.
    """
    actions = []
    current_time = datetime.now()
    
    for sym, pos in active_positions.items():
        # 1. WRONG WAY CORRECTOR (Sentiment Mismatch)
        roi = (pos['pnl'] / (abs(pos['amt']) * pos['entry'])) if pos['entry'] > 0 else 0
        
        # Case 1: Holding LONG in Deep Bear Market
        if global_sentiment < 0.25 and pos['amt'] > 0 and roi < -0.015:
            actions.append({
                'symbol': sym,
                'side': 'sell',
                'amount': abs(pos['amt']),
                'price': pos.get('price', pos['entry']), # Best effort price
                'reason': f"SENTIMENT_MISMATCH_BEAR (Sent {global_sentiment:.2f})",
                'reduceOnly': True
            })
            continue # Skip other checks for this symbol
        
        # Case 2: Holding SHORT in Strong Bull Market
        elif global_sentiment > 0.75 and pos['amt'] < 0 and roi < -0.015:
            actions.append({
                'symbol': sym,
                'side': 'buy',
                'amount': abs(pos['amt']),
                'price': pos.get('price', pos['entry']),
                'reason': f"SENTIMENT_MISMATCH_BULL (Sent {global_sentiment:.2f})",
                'reduceOnly': True
            })
            continue

        # 2. TOXIC ASSET PURGE (High Loss Velocity)
        # If a position loses > 5% ROI in less than 30 minutes, kill it.
        if 'entry_time' not in pos:
            pos['entry_time'] = current_time.isoformat()
        
        try:
            entry_t = datetime.fromisoformat(pos['entry_time'])
            duration_minutes = (current_time - entry_t).total_seconds() / 60
            duration_hours = duration_minutes / 60
            
            if duration_minutes < 30 and roi < -0.05:
                side = 'sell' if pos['amt'] > 0 else 'buy'
                actions.append({
                    'symbol': sym,
                    'side': side,
                    'amount': abs(pos['amt']),
                    'price': pos.get('price', pos['entry']),
                    'reason': f"TOXIC_ASSET_PURGE (Drop {roi*100:.1f}% in {duration_minutes:.0f}m)",
                    'reduceOnly': True
                })
                continue

        except:
            pass
            
    return actions
