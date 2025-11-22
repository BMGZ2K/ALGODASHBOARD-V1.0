import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import json
import time
import os
from datetime import datetime

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Gemini 3.0 Pro Terminal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .stApp {
        background-color: #0e1117;
    }
    .metric-card {
        background-color: #1e2127;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #2e3137;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .stDataFrame {
        border: 1px solid #2e3137;
        border-radius: 5px;
    }
    h1, h2, h3 {
        color: #e0e0e0;
        font-family: 'Inter', sans-serif;
    }
    .status-badge {
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 0.8em;
    }
    .status-ok { background-color: #1c4a28; color: #4ade80; }
    .status-warn { background-color: #4a3a1c; color: #facc15; }
    .status-err { background-color: #4a1c1c; color: #f87171; }
    </style>
""", unsafe_allow_html=True)

# --- PATHS ---
STATE_FILE = "state/dashboard_state.json"
LOG_FILE = "logs/trades_log.csv"
BOT_OUTPUT_LOG = "logs/bot_output.log"
STRATEGY_LOG_FILE = "logs/strategy_analysis.log"
HISTORY_FILE = "logs/balance_history.csv"

# --- HELPER FUNCTIONS ---
def load_json(filepath):
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}

def get_status_color(val, threshold_low, threshold_high, inverse=False):
    if inverse:
        if val < threshold_low: return "green"
        if val < threshold_high: return "orange"
        return "red"
    else:
        if val > threshold_high: return "green"
        if val > threshold_low: return "orange"
        return "red"

# --- SIDEBAR ---
with st.sidebar:
    st.title("⚡ Gemini 3.0")
    st.caption("Advanced Algo-Trading System")
    
    state = load_json(STATE_FILE)
    last_update = state.get('timestamp', 'N/A')
    
    # System Health
    st.subheader("System Health")
    
    # Check staleness
    is_stale = False
    try:
        last_ts = pd.to_datetime(last_update)
        latency = (pd.Timestamp.now() - last_ts).total_seconds()
        if latency > 30:
            is_stale = True
            st.error(f"🔴 System Stale ({latency:.0f}s ago)")
        else:
            st.success(f"🟢 Online ({latency:.1f}s latency)")
    except:
        st.warning("⚪ Initializing...")

    # Controls
    st.divider()
    st.subheader("Controls")
    refresh_rate = 1 # Fixed 1s refresh for real-time updates

    
    if st.button("🔄 Force Refresh"):
        st.rerun()
        
    st.divider()
    st.subheader("Emergency")
    panic_confirm = st.checkbox("Arm Panic Button")
    if st.button("🚨 CLOSE ALL POSITIONS", type="primary", disabled=not panic_confirm):
        with open("state/bot_commands.json", "w") as f:
            json.dump({"command": "CLOSE_ALL"}, f)
        st.toast("🚨 PANIC COMMAND SENT!", icon="🔥")

# --- MAIN CONTENT ---
# Top Metrics Row
col1, col2, col3, col4 = st.columns(4)

balance = state.get('balance', 0.0)
avail = state.get('available_balance', 0.0)
pnl = state.get('realized_pnl', 0.0)
positions = state.get('positions', {})
sentiment = state.get('sentiment', 0.5)

with col1:
    st.metric("Total Balance", f"${balance:,.2f}", delta=f"{pnl:,.2f} Session", delta_color="normal")
with col2:
    margin_used = balance - avail
    margin_pct = (margin_used / balance) * 100 if balance > 0 else 0
    st.metric("Margin Used", f"{margin_pct:.1f}%", f"${avail:,.2f} Free", delta_color="normal")
with col3:
    open_pnl = sum(p['pnl'] for p in positions.values())
    st.metric("Open PnL", f"${open_pnl:,.2f}", delta=f"{open_pnl:,.2f}", delta_color="normal")
with col4:
    sent_color = "off"
    if sentiment > 0.6: sent_text = "BULLISH"; sent_color = "normal"
    elif sentiment < 0.4: sent_text = "BEARISH"; sent_color = "inverse"
    else: sent_text = "NEUTRAL"; sent_color = "off"
    st.metric("Market Sentiment", f"{sentiment:.2f}", sent_text, delta_color=sent_color)

# --- TABS ---
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📈 Dashboard", "📊 Analytics", "🔎 Scanner", "📝 Logs", "🧠 Strategy Analysis"])

with tab1:
    # Active Positions
    st.subheader(f"Active Positions ({len(positions)})")
    
    if positions:
        pos_data = []
        for sym, data in positions.items():
            entry = data['entry']
            price = data.get('price', entry) # Fallback
            pnl = data['pnl']
            amt = data['amt']
            roi = (pnl / (abs(amt) * entry / 5)) * 100 if entry > 0 else 0 # Est 5x lev
            
            pos_data.append({
                "Symbol": sym,
                "Side": "LONG" if amt > 0 else "SHORT",
                "Size": abs(amt),
                "Entry": entry,
                "PnL": pnl,
                "ROI": roi,
                "Duration": data.get('entry_time', 'N/A')
            })
        
        df_pos = pd.DataFrame(pos_data)
        
        st.dataframe(
            df_pos,
            column_config={
                "Symbol": st.column_config.TextColumn("Pair", help="Trading Pair"),
                "Side": st.column_config.TextColumn("Side"),
                "Size": st.column_config.NumberColumn("Size", format="%.4f"),
                "Entry": st.column_config.NumberColumn("Entry", format="$%.4f"),
                "PnL": st.column_config.NumberColumn("PnL (USDT)", format="$%.2f"),
                "ROI": st.column_config.ProgressColumn("ROI %", format="%.2f%%", min_value=-100, max_value=100),
            },
            use_container_width=True 
        )
    else:
        st.info("✨ No active positions. Scanning for opportunities...")

    # Charts Row
    c1, c2 = st.columns(2)
    
    if os.path.exists(HISTORY_FILE):
        try:
            df_hist = pd.read_csv(HISTORY_FILE)
            df_hist['timestamp'] = pd.to_datetime(df_hist['timestamp'], format='mixed', errors='coerce')
            
            # Ensure numeric columns
            cols_to_numeric = ['balance', 'open_pnl']
            for col in cols_to_numeric:
                if col in df_hist.columns:
                    df_hist[col] = pd.to_numeric(df_hist[col], errors='coerce')
            
            # Drop rows with invalid timestamp or critical data
            df_hist.dropna(subset=['timestamp', 'balance', 'open_pnl'], inplace=True)
            
            if not df_hist.empty:
                with c1:
                    st.subheader("Balance Growth")
                    fig_bal = px.area(df_hist, x='timestamp', y='balance', template="plotly_dark", line_shape='spline')
                    fig_bal.update_traces(line_color='#4ade80', fillcolor='rgba(74, 222, 128, 0.2)')
                    fig_bal.update_layout(height=300, margin=dict(l=0, r=0, t=0, b=0))
                    st.plotly_chart(fig_bal, use_container_width=True)
                    
                with c2:
                    st.subheader("Open PnL History")
                    fig_pnl = px.area(df_hist, x='timestamp', y='open_pnl', template="plotly_dark", line_shape='spline')
                    fig_pnl.update_traces(line_color='#60a5fa', fillcolor='rgba(96, 165, 250, 0.2)')
                    fig_pnl.update_layout(height=300, margin=dict(l=0, r=0, t=0, b=0))
                    st.plotly_chart(fig_pnl, use_container_width=True)
            else:
                st.info("Not enough history data to chart.")
                
        except Exception as e:
            st.error(f"Chart Error: {e}")

with tab2:
    st.subheader("Performance Analytics")
    if os.path.exists(LOG_FILE):
        try:
            df_trades = pd.read_csv(LOG_FILE)
            # Filter for FILLED trades
            df_filled = df_trades[df_trades['status'].str.contains('FILLED', na=False)].copy()
            
            # Ensure PnL column exists (for backward compatibility)
            if 'pnl' not in df_filled.columns:
                df_filled['pnl'] = 0.0
            
            # Fill NaNs in PnL with 0
            df_filled['pnl'] = df_filled['pnl'].fillna(0.0)
            
            if not df_filled.empty:
                # --- METRICS ---
                col_a1, col_a2, col_a3, col_a4 = st.columns(4)
                
                total_trades = len(df_filled)
                total_vol = (df_filled['price'] * df_filled['amount']).sum()
                avg_size = total_vol / total_trades if total_trades > 0 else 0
                total_realized_pnl = df_filled['pnl'].sum()
                
                with col_a1:
                    st.metric("Total Trades", total_trades)
                with col_a2:
                    st.metric("Volume Traded", f"${total_vol:,.2f}")
                with col_a3:
                    st.metric("Avg Trade Size", f"${avg_size:,.2f}")
                with col_a4:
                    st.metric("Realized PnL", f"${total_realized_pnl:,.2f}", 
                              delta=f"{total_realized_pnl:,.2f}", delta_color="normal")
                
                st.divider()
                
                # --- DETAILED TRADE HISTORY ---
                st.subheader("Trade History")
                
                # Format Timestamp
                df_filled['timestamp'] = pd.to_datetime(df_filled['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
                
                # Select and Rename Columns for Display
                df_display = df_filled[['timestamp', 'symbol', 'side', 'price', 'amount', 'pnl', 'reason']].copy()
                df_display.columns = ['Time', 'Symbol', 'Side', 'Price', 'Size', 'Realized PnL', 'Reason']
                
                # Sort by Time Descending
                df_display = df_display.sort_values('Time', ascending=False)

                st.dataframe(
                    df_display,
                    column_config={
                        "Time": st.column_config.TextColumn("Time"),
                        "Symbol": st.column_config.TextColumn("Pair"),
                        "Side": st.column_config.TextColumn("Side"),
                        "Price": st.column_config.NumberColumn("Price", format="$%.4f"),
                        "Size": st.column_config.NumberColumn("Size", format="%.4f"),
                        "Realized PnL": st.column_config.NumberColumn("Realized PnL", format="$%.2f"),
                        "Reason": st.column_config.TextColumn("Signal/Reason"),
                    },
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("No trade history available yet.")
        except Exception as e:
            st.error(f"Error loading analytics: {e}")
    else:
        st.info("Log file not found.")

with tab3:
    st.subheader("Market Scanner")
    scan_data = state.get('market_scan', {})
    if scan_data:
        rows = []
        for sym, data in scan_data.items():
            rows.append({
                "Symbol": sym,
                "Price": data['price'],
                "Trend": data['trend'],
                "RSI": data['rsi'],
                "ADX": data['adx'],
                "Signal": data['signal']
            })
        
        df_scan = pd.DataFrame(rows)
        st.dataframe(
            df_scan,
            column_config={
                "Price": st.column_config.NumberColumn("Price", format="$%.4f"),
                "RSI": st.column_config.ProgressColumn("RSI", min_value=0, max_value=100, format="%.1f"),
                "ADX": st.column_config.NumberColumn("ADX", format="%.1f"),
                "Trend": st.column_config.TextColumn("Trend"),
            },
            use_container_width=True
        )
    else:
        st.warning("Scanner initializing...")

with tab4:
    st.subheader("System Logs")
    if os.path.exists(BOT_OUTPUT_LOG):
        with open(BOT_OUTPUT_LOG, "r") as f:
            lines = f.readlines()[-50:]
            st.code("".join(lines), language="text")

with tab5:
    st.subheader("Strategy Decision Logic")
    st.caption("Detailed breakdown of why trades were taken or rejected.")
    
    if st.button("🗑️ Clear Strategy Log"):
        open(STRATEGY_LOG_FILE, 'w').close()
        st.toast("Log Cleared!")
        st.rerun()
        
    if os.path.exists(STRATEGY_LOG_FILE):
        with open(STRATEGY_LOG_FILE, "r") as f:
            # Read last 200 lines to avoid huge load
            lines = f.readlines()[-200:]
            # Reverse to show newest first
            lines.reverse() 
            
            log_content = "".join(lines)
            st.text_area("Analysis Log (Newest First)", log_content, height=600)
    else:
        st.info("No strategy analysis logs found yet.")

# Auto-Refresh
time.sleep(refresh_rate)
st.rerun()
