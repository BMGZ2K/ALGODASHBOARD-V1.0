#!/bin/bash
# Kills any existing instances
echo "Stopping existing processes..."
pkill -f "run_live.py"
pkill -f "streamlit"
# Force kill port 8501 if still in use
fuser -k 8501/tcp > /dev/null 2>&1

# Wait a moment for ports to clear
sleep 2

# Starts the bot in background
echo "Starting Trading Bot..."
nohup venv/bin/python -u run_live.py > bot_output.log 2>&1 &
echo "🤖 Bot started in background (PID $!)"

# Starts the dashboard
echo "Starting Web Dashboard..."
venv/bin/streamlit run dashboard.py --server.port 8501 --server.address 0.0.0.0 --server.headless true > dashboard.log 2>&1 &
