from tools.wfo import Strategy
import pandas_ta as ta
import pandas as pd
import numpy as np

class HybridStrategy(Strategy):
    def generate_signals(self, df):
        # Params: 
        # Trend (4h): st_len, st_mult
        # Pullback (15m): rsi_len, rsi_buy
        # Breakout (15m): breakout_window
        
        st_len = self.params.get('st_len', 10)
        st_mult = self.params.get('st_mult', 3.0)
        rsi_len = self.params.get('rsi_len', 14)
        rsi_buy = self.params.get('rsi_buy', 40)
        breakout_window = self.params.get('breakout_window', 96) # 24h in 15m candles
        
        # 1. Resample to 4h for Trend
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
            
        agg_dict = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}
        df_4h = df.resample('4h').agg(agg_dict).dropna()
        
        st = ta.supertrend(df_4h['high'], df_4h['low'], df_4h['close'], length=st_len, multiplier=st_mult)
        st_dir_col = f"SUPERTd_{st_len}_{st_mult}"
        if st_dir_col not in st.columns:
             cols = [c for c in st.columns if c.startswith('SUPERTd')]
             if cols: st_dir_col = cols[0]
        
        trend_series = st[st_dir_col].reindex(df.index).ffill()
        
        # 2. Pullback Indicators
        rsi = ta.rsi(df['close'], length=rsi_len)
        
        # 3. Breakout Indicators
        # Donchian Channel High/Low (Previous N candles)
        high_rolling = df['high'].rolling(window=breakout_window).max().shift(1)
        low_rolling = df['low'].rolling(window=breakout_window).min().shift(1)
        
        position = np.zeros(len(df))
        curr_pos = 0
        trend_vals = trend_series.values
        rsi_vals = rsi.values
        high_vals = high_rolling.values
        low_vals = low_rolling.values
        close_vals = df['close'].values
        
        for i in range(1, len(df)):
            trend_dir = trend_vals[i] # 1 (Up) or -1 (Down)
            
            if curr_pos == 0:
                # --- LONG Logic ---
                if trend_dir == 1:
                    # Pullback (Oversold) OR Breakout (New High)
                    if rsi_vals[i] < rsi_buy or close_vals[i] > high_vals[i]:
                        curr_pos = 1
                        
                # --- SHORT Logic ---
                elif trend_dir == -1:
                    # Pullback (Overbought in downtrend) OR Breakout (New Low)
                    # RSI Sell Level typically > 60 for downtrend pullbacks
                    rsi_sell_lvl = 100 - rsi_buy # Symmetry (e.g. 40 -> 60)
                    
                    if rsi_vals[i] > rsi_sell_lvl or close_vals[i] < low_vals[i]:
                        curr_pos = -1
                    
            elif curr_pos == 1:
                # Exit Long: Trend breaks (becomes -1)
                if trend_dir == -1:
                    curr_pos = 0
                    # Reverse immediately? Usually better to wait for setup.
                    # For simplistic strategy, we just exit to 0.
            
            elif curr_pos == -1:
                # Exit Short: Trend breaks (becomes 1)
                if trend_dir == 1:
                    curr_pos = 0
            
            position[i] = curr_pos
            
        return pd.Series(position, index=df.index)
