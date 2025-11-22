from tools.wfo import Strategy
import pandas_ta as ta
import pandas as pd
import numpy as np

class RSI2Strategy(Strategy):
    def generate_signals(self, df):
        # Params: rsi_len, buy_lvl, sell_lvl, exit_ma
        rsi_len = self.params.get('rsi_len', 2)
        buy_lvl = self.params.get('buy_lvl', 10)
        sell_lvl = self.params.get('sell_lvl', 90)
        ma_len = self.params.get('exit_ma', 5)
        
        # Indicators
        df['rsi'] = ta.rsi(df['close'], length=rsi_len)
        df['ma_exit'] = ta.sma(df['close'], length=ma_len)
        # Trend Filter (200 SMA) - Only buy if price > 200 SMA?
        # For high freq, maybe we skip trend filter or make it optional.
        df['ma_trend'] = ta.sma(df['close'], length=200)
        
        rsi = df['rsi'].values
        close = df['close'].values
        ma_exit = df['ma_exit'].values
        ma_trend = df['ma_trend'].values
        
        position = np.zeros(len(df))
        curr_pos = 0
        
        for i in range(1, len(df)):
            if np.isnan(rsi[i]) or np.isnan(ma_exit[i]) or np.isnan(ma_trend[i]):
                continue
            
            # Trend Filter: Only Long if Price > SMA 200
            uptrend = close[i] > ma_trend[i]
            
            if curr_pos == 0:
                # Long Entry
                if rsi[i] < buy_lvl and uptrend:
                    curr_pos = 1
                # Short Entry (Inverse) - Optional, usually RSI2 is Long Only in stocks, but Crypto allows both.
                # Let's try Long Only first as it's safer? 
                # Or Short if downtrend?
                elif rsi[i] > sell_lvl and not uptrend:
                    curr_pos = -1
            
            elif curr_pos == 1:
                # Exit Long: Price > MA Exit
                if close[i] > ma_exit[i]:
                    curr_pos = 0
            
            elif curr_pos == -1:
                # Exit Short: Price < MA Exit
                if close[i] < ma_exit[i]:
                    curr_pos = 0
            
            position[i] = curr_pos
            
        return pd.Series(position, index=df.index)
