from tools.wfo import Strategy
import pandas_ta as ta
import pandas as pd
import numpy as np

class SuperTrendStrategy(Strategy):
    def generate_signals(self, df):
        # Params: length, multiplier
        length = self.params.get('length', 10)
        multiplier = self.params.get('multiplier', 3.0)
        
        # Indicator
        st = ta.supertrend(df['high'], df['low'], df['close'], length=length, multiplier=multiplier)
        
        # Supertrend returns 4 columns: SUPERT_l_m, SUPERTd_l_m, SUPERTl_l_m, SUPERTs_l_m
        # We need the direction column (SUPERTd) or the trend line (SUPERT)
        # Usually column 1 is direction (1 for Up, -1 for Down)
        
        st_dir_col = f"SUPERTd_{length}_{multiplier}"
        if st_dir_col not in st.columns:
            # Fallback: try to find the direction column by name pattern
            cols = [c for c in st.columns if c.startswith('SUPERTd')]
            if cols:
                st_dir_col = cols[0]
            else:
                return pd.Series(0, index=df.index)
                
        df = pd.concat([df, st], axis=1)
        
        direction = df[st_dir_col].values
        
        # Logic: 
        # If Direction == 1 -> Long
        # If Direction == -1 -> Cash (Long Only) or Short
        
        long_only = self.params.get('long_only', True)
        
        position = np.zeros(len(df))
        
        for i in range(len(df)):
            if direction[i] == 1:
                position[i] = 1
            elif direction[i] == -1:
                if long_only:
                    position[i] = 0
                else:
                    position[i] = -1
            else:
                # Maintain previous if unknown (though supertrend is usually always 1 or -1)
                if i > 0:
                    position[i] = position[i-1]
                    
        return pd.Series(position, index=df.index)
