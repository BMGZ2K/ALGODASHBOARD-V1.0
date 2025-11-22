from tools.wfo import Strategy
import pandas_ta as ta
import pandas as pd
import numpy as np

class SmartHybridStrategy(Strategy):
    def generate_signals(self, df):
        # Params:
        # Trend (4h): st_len, st_mult
        # Pullback (15m): rsi_len, rsi_buy
        # Volatility: atr_len, atr_mult (for TP)
        
        st_len = self.params.get('st_len', 10)
        st_mult = self.params.get('st_mult', 3.0)
        rsi_len = self.params.get('rsi_len', 14)
        rsi_buy = self.params.get('rsi_buy', 40)
        atr_len = self.params.get('atr_len', 14)
        tp_mult = self.params.get('tp_mult', 3.0) # TP at 3x ATR
        
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
        
        # 2. Indicators
        rsi = ta.rsi(df['close'], length=rsi_len)
        atr = ta.atr(df['high'], df['low'], df['close'], length=atr_len)
        
        position = np.zeros(len(df))
        curr_pos = 0
        entry_price = 0.0
        
        trend_vals = trend_series.values
        rsi_vals = rsi.values
        atr_vals = atr.values
        close_vals = df['close'].values
        high_vals = df['high'].values
        low_vals = df['low'].values
        
        for i in range(1, len(df)):
            trend_dir = trend_vals[i]
            
            if curr_pos == 0:
                # --- LONG Logic ---
                if trend_dir == 1:
                    # Pullback Entry
                    if rsi_vals[i] < rsi_buy:
                        curr_pos = 1
                        entry_price = close_vals[i]
                        
                # --- SHORT Logic ---
                elif trend_dir == -1:
                    rsi_sell_lvl = 100 - rsi_buy
                    if rsi_vals[i] > rsi_sell_lvl:
                        curr_pos = -1
                        entry_price = close_vals[i]
                    
            elif curr_pos == 1:
                # 1. Trend Reversal (Stop Loss / Exit)
                if trend_dir == -1:
                    curr_pos = 0
                
                # 2. Take Profit (ATR based)
                elif tp_mult > 0:
                    tp_price = entry_price + (atr_vals[i] * tp_mult)
                    if high_vals[i] >= tp_price:
                        curr_pos = 0 # TP Hit
            
            elif curr_pos == -1:
                # 1. Trend Reversal
                if trend_dir == 1:
                    curr_pos = 0
                
                # 2. Take Profit
                elif tp_mult > 0:
                    tp_price = entry_price - (atr_vals[i] * tp_mult)
                    if low_vals[i] <= tp_price:
                        curr_pos = 0 # TP Hit
            
            position[i] = curr_pos
            
        return pd.Series(position, index=df.index)
