import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import time
import os

st.set_page_config(
    page_title="Gemini 3.0 Algo Dashboard",
    page_icon="🚀",
    layout="wide",
)

st.title("🚀 Gemini 3.0: Live Trading Dashboard")

# --- 1. READ STATE ---
STATE_FILE = "dashboard_state.json"
LOG_FILE = "trades_log.csv"
BOT_OUTPUT_LOG = "bot_output.log"

# Default State Function
def get_default_state():
    return {
        'timestamp': "Waiting...",
        'symbol': "LOADING",
        'price': 0.0,
        'trend': 0,
        'rsi': 50,
        'breakout_level': 0,
        'position': 0.0,
        'pnl': 0.0,
        'entry_price': 0.0,
        'trailing_active': False,
        'trailing_stop': 0.0,
        'mode': 'OFFLINE'
    }

if not os.path.exists(STATE_FILE):
    state = get_default_state()
    st.warning("Bot offline or initializing...")
else:
    try:
        with open(STATE_FILE, 'r') as f:
            state = json.load(f)
    except:
        state = get_default_state()

# Check for staleness (if data is older than 30 seconds)
is_stale = False
try:
    last_update = pd.to_datetime(state['timestamp'])
    if (pd.Timestamp.now() - last_update).total_seconds() > 30:
        is_stale = True
except:
    pass

if is_stale:
    st.error("⚠️ Data might be stale! Bot may have stopped.")

# --- 1. PORTFOLIO OVERVIEW ---
st.subheader("Portfolio Overview")
col1, col2, col3, col4, col5, col6 = st.columns(6)

balance = state.get('balance', 0.0)
positions = state.get('positions', {})
sentiment = state.get('sentiment', 0.5)
realized_pnl = state.get('realized_pnl', 0.0)
available_margin = state.get('available_balance', 0.0)

longs = sum(1 for p in positions.values() if p['amt'] > 0)
shorts = sum(1 for p in positions.values() if p['amt'] < 0)
total_pnl = sum(p['pnl'] for p in positions.values())

with col1:
    st.metric("Total Balance (USDT)", f"${balance:.2f}")

with col2:
    st.metric("Realized PnL (Session)", f"${realized_pnl:.2f}", delta=f"{realized_pnl:.2f}")

with col3:
    st.metric("Available Margin", f"${available_margin:.2f}")

with col4:
    st.metric("Active Positions", f"{len(positions)} / 20")

with col5:
    total_open_pnl = sum(p['pnl'] for p in positions.values())
    st.metric("Total Open PnL", f"${total_open_pnl:.2f}", delta=f"{total_open_pnl:.2f}")

with col6:
    longs = sum(1 for p in positions.values() if p['amt'] > 0)
    shorts = sum(1 for p in positions.values() if p['amt'] < 0)
    st.metric("L/S Exposure", f"{longs}L | {shorts}S")

# --- AUTO-PILOT STATUS ---
st.info(f"🤖 **AUTO-PILOT ACTIVE** | Risk: 2.0% | Max Pos: 20 | Lev Cap: 5x | Heikin Ashi: ON")

# --- ACTIVE POSITIONS ---
if positions:
    st.subheader(f"📋 Active Positions ({len(positions)})")
    pos_data = []
    for sym, data in positions.items():
        pos_data.append({
            "Symbol": sym,
            "Size": f"{data['amt']:.4f}",
            "Entry": f"${data['entry']:.4f}",
            "PnL": f"${data['pnl']:.2f}"
        })
    st.dataframe(pd.DataFrame(pos_data), use_container_width=True)
else:
    st.info("No active positions. Scanning...")

# --- 2. ACCOUNT PERFORMANCE ---
st.subheader("Account Performance")
HISTORY_FILE = "balance_history.csv"

if os.path.exists(HISTORY_FILE):
    try:
        df_hist = pd.read_csv(HISTORY_FILE)
        df_hist['timestamp'] = pd.to_datetime(df_hist['timestamp'])
        df_hist = df_hist.set_index('timestamp')
        
        # Resample to 1min or keep raw if not too dense
        # For now, just show last 100 points
        df_show = df_hist.tail(200)
        
        col_h1, col_h2 = st.columns(2)
        
        with col_h1:
            st.write("**Balance Growth**")
            st.line_chart(df_show['balance'], color='#00FF00')
            
        with col_h2:
            st.write("**Open PnL & Sentiment**")
            # Normalize sentiment to match PnL scale? No, separate chart better.
            # Let's just show PnL here
            st.area_chart(df_show['open_pnl'], color='#FFA500')
            
        st.caption(f"Tracking {len(df_hist)} data points.")
            
    except Exception as e:
        st.error(f"Error loading history: {e}")
else:
    st.info("Waiting for history data...")

# --- 3. MARKET SCANNER ---
st.subheader("Market Scanner (Real-Time)")
scan_data = state.get('market_scan', {})

if scan_data:
    rows = []
    for sym, data in scan_data.items():
        trend_icon = "⬆️" if data['trend'] == 'BULL' else ("⬇️" if data['trend'] == 'BEAR' else "➡️")
        signal_color = "🟢" if "LONG" in data['signal'] else ("🔴" if "SHORT" in data['signal'] else "⚪")
        
        # Determine sort priority: Active Signals > High ADX > Others
        priority = 0
        if "LONG" in data['signal'] or "SHORT" in data['signal']: priority = 2
        elif data['adx'] > 25: priority = 1
        
        rows.append({
            "Symbol": sym,
            "Price": f"${data['price']:.2f}",
            "Trend": f"{trend_icon} {data['trend']}",
            "RSI": f"{data['rsi']:.1f}",
            "ADX": f"{data['adx']:.1f}",
            "Signal": f"{signal_color} {data['signal']}",
            "_priority": priority # Hidden sort column
        })
    
    df_scan = pd.DataFrame(rows)
    # Sort by priority (descending)
    df_scan = df_scan.sort_values(by='_priority', ascending=False).drop(columns=['_priority'])
    
    st.dataframe(df_scan, use_container_width=True, height=500)
else:
    st.warning("Waiting for scanner data...")

# --- 4. SYSTEM STATUS & CONTROLS ---
st.subheader("System Status & Controls")
col_s1, col_s2 = st.columns(2)

with col_s1:
    blacklist = state.get('blacklist', [])
    if blacklist:
        st.error(f"🚫 Blacklisted Symbols ({len(blacklist)}): {', '.join(blacklist)}")
    else:
        st.success("✅ System Healthy: No Blacklisted Symbols")

with col_s2:
    st.write("**Emergency Controls**")
    if st.button("🚨 CLOSE ALL POSITIONS (PANIC)", type="primary"):
        with open("bot_commands.json", "w") as f:
            json.dump({"command": "CLOSE_ALL"}, f)
        st.warning("Command Sent! Waiting for bot to execute...")

# --- 5. PERFORMANCE METRICS ---
st.subheader("Performance Metrics")
col_p1, col_p2, col_p3 = st.columns(3)

if os.path.exists(LOG_FILE):
    try:
        df_trades = pd.read_csv(LOG_FILE)
        total_trades = len(df_trades)
        last_trade = df_trades.iloc[-1]['timestamp'] if not df_trades.empty else "N/A"
        
        # Simple Win Rate Estimation (very rough, assumes alternating buy/sell for same symbol)
        # This is just a placeholder for now until we have a proper closed trade log
        
        with col_p1:
            st.metric("Total Executions", total_trades)
        with col_p2:
            st.metric("Last Activity", last_trade.split('T')[-1].split('.')[0] if 'T' in last_trade else last_trade)
        with col_p3:
            st.metric("Active Symbols", len(state.get('positions', {})))
            
    except Exception as e:
        st.error(f"Error calculating metrics: {e}")

# --- 4. LOGS ---
st.subheader("Bot Activity Logs")
col_logs, col_term = st.columns(2)

with col_logs:
    st.write("Recent Trades")
    if os.path.exists(LOG_FILE):
        try:
            df_trades = pd.read_csv(LOG_FILE)
            st.dataframe(df_trades.tail(10).sort_index(ascending=False))
        except Exception as e:
            st.error(f"Error reading log file: {e}")
    else:
        st.info("No trades logged yet.")

with col_term:
    st.subheader("Bot Terminal Output")
    if os.path.exists(BOT_OUTPUT_LOG):
        try:
            # Read last 20 lines
            with open(BOT_OUTPUT_LOG, "r") as f:
                lines = f.readlines()
                last_lines = lines[-20:]
                st.text_area("Last 20 lines", "".join(last_lines), height=300)
        except Exception as e:
            st.error(f"Error reading output log: {e}")
    else:
        st.info("No terminal output found.")

# --- 5. FOOTER ---
st.markdown("---")
st.caption(f"Last Update: {state['timestamp']} | Engine: Python 3.10+ | UI: Streamlit")

# --- AUTO-REFRESH ---
time.sleep(2)
st.rerun()
