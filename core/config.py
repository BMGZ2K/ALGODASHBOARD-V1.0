import os
from dotenv import load_dotenv

# Load Environment Variables
load_dotenv(override=True)

# Configuration
USE_TESTNET = os.getenv('TESTNET', 'True').lower() == 'true'
API_KEY = os.getenv('Binanceapikey', '').strip()
SECRET_KEY = os.getenv('BinanceSecretkey', '').strip()
LOG_FILE = "logs/trades_log.csv"
SESSION_FILE = "state/session_info.json"
STATE_FILE = "state/dashboard_state.json"
HISTORY_FILE = "logs/balance_history.csv"
COMMAND_FILE = "state/bot_commands.json"
BOT_OUTPUT_LOG = "logs/bot_output.log"

# Top 35 Liquid Futures Pairs (Cleaned)
SYMBOLS = [
    'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'DOGE/USDT',
    'XRP/USDT', 'ADA/USDT', 'AVAX/USDT', 'DOT/USDT', 'LINK/USDT',
    'LTC/USDT', 'TRX/USDT', 'UNI/USDT', 'ATOM/USDT', 'NEAR/USDT',
    'APT/USDT', 'FIL/USDT', 'SUI/USDT', 'ARB/USDT', 'OP/USDT',
    'INJ/USDT', 'STX/USDT', 'IMX/USDT', 'GRT/USDT', 'SNX/USDT',
    'VET/USDT', 'THETA/USDT', 'LDO/USDT', 'TIA/USDT', 'SEI/USDT',
    'ORDI/USDT', 'FET/USDT', 'ALGO/USDT', 'FLOW/USDT', 'XLM/USDT',
    'CRV/USDT', '1000PEPE/USDT', 'RUNE/USDT', 'ETC/USDT', 'ICP/USDT',
    'SAND/USDT', 'MANA/USDT', 'AXS/USDT', 'EGLD/USDT', 'AAVE/USDT',
    'EOS/USDT', 'QNT/USDT', 'GALA/USDT', 'FTM/USDT', 'MATIC/USDT',
    'DYDX/USDT', 'APE/USDT', 'CHZ/USDT', 'KAVA/USDT', 'XTZ/USDT',
    '1000SHIB/USDT', '1000FLOKI/USDT', '1000BONK/USDT'
]

# Strategy Config
DEFAULT_STRATEGY_CONFIG = {
    'st_len': 10, 
    'st_mult': 3.0, 
    'rsi_len': 14, 
    'rsi_buy': 40, 
    'breakout_window': 96
}

# Risk Config
MAX_POSITIONS = 20
LEVERAGE_CAP = 5
RISK_PER_TRADE = 0.015
COOLDOWN_MINUTES = 15
CIRCUIT_BREAKER_DRAWDOWN = 0.25
