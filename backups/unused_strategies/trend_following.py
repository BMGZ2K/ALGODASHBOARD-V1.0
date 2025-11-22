from tools.wfo import Strategy
import pandas_ta as ta
import pandas as pd
import numpy as np

class TrendFollowingStrategy(Strategy):
    def generate_signals(self, df):
        # Params: fast_ema, slow_ema
        fast = self.params.get('fast_ema', 20)
        slow = self.params.get('slow_ema', 50)
        
        # Indicators
        df['ema_fast'] = ta.ema(df['close'], length=fast)
        df['ema_slow'] = ta.ema(df['close'], length=slow)
        
        # Ensure numeric and fillna
        df['ema_fast'] = pd.to_numeric(df['ema_fast'], errors='coerce')
        df['ema_slow'] = pd.to_numeric(df['ema_slow'], errors='coerce')
        
        ema_fast = df['ema_fast'].values
        ema_slow = df['ema_slow'].values
        
        position = np.zeros(len(df))
        curr_pos = 0
        
        # Logic: Always in the market (Long or Short)
        # or only enter on crossover?
        # Let's do Always In (Stop and Reverse).
        
        long_only = self.params.get('long_only', True) # Default to Long Only for Spot
        
        for i in range(1, len(df)):
            # Robust check for NaN using pandas built-in or math.isnan if scalar
            # But since we converted to numeric, np.isnan should work if it's float.
            # If it failed before, maybe it was object type with None.
            
            if np.isnan(ema_fast[i]) or np.isnan(ema_slow[i]):
                continue
                
            if ema_fast[i] > ema_slow[i]:
                curr_pos = 1
            elif ema_fast[i] < ema_slow[i]:
                if long_only:
                    curr_pos = 0 # Exit to Cash
                else:
                    curr_pos = -1 # Short
            
            position[i] = curr_pos
            
        return pd.Series(position, index=df.index)

