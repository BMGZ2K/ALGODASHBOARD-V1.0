from tools.wfo import Strategy
import pandas_ta as ta
import pandas as pd
import numpy as np

class MeanReversionFilteredStrategy(Strategy):
    def generate_signals(self, df):
        # Params: bb_len, bb_std, adx_threshold
        bb_len = self.params.get('bb_len', 20)
        bb_std = self.params.get('bb_std', 2.5)
        adx_thres = self.params.get('adx_threshold', 25)
        
        # Indicators
        bb = ta.bbands(df['close'], length=bb_len, std=bb_std)
        if bb is None: return pd.Series(0, index=df.index)
        
        lower_col = bb.columns[0] 
        mid_col = bb.columns[1]
        upper_col = bb.columns[2] 
        
        # ADX
        adx = ta.adx(df['high'], df['low'], df['close'], length=14)
        adx_col = adx.columns[0]
        
        df = pd.concat([df, bb, adx], axis=1)
        
        # Logic with State
        close = df['close'].values
        lower = df[lower_col].values
        upper = df[upper_col].values
        mid = df[mid_col].values
        adx_vals = df[adx_col].values
        
        position = np.zeros(len(df))
        curr_pos = 0
        
        for i in range(1, len(df)):
            # Entry Logic
            if curr_pos == 0:
                # Only enter if ADX is low
                if adx_vals[i] < adx_thres:
                    if close[i] < lower[i]:
                        curr_pos = 1
                    elif close[i] > upper[i]:
                        curr_pos = -1
            
            # Exit Logic
            elif curr_pos == 1:
                # Exit Long if Price > Mid
                if close[i] > mid[i]:
                    curr_pos = 0
                    
            elif curr_pos == -1:
                # Exit Short if Price < Mid
                if close[i] < mid[i]:
                    curr_pos = 0
            
            position[i] = curr_pos
            
        return pd.Series(position, index=df.index)

