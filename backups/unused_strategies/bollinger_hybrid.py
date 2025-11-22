from tools.wfo import Strategy
import pandas_ta as ta
import pandas as pd
import numpy as np

class BollingerHybridStrategy(Strategy):
    def generate_signals(self, df):
        # Params:
        # Trend (4h): st_len, st_mult
        # Bollinger (15m): bb_len, bb_std
        # RSI (15m): rsi_len, rsi_buy
        
        st_len = self.params.get('st_len', 10)
        st_mult = self.params.get('st_mult', 3.0)
        bb_len = self.params.get('bb_len', 20)
        bb_std = self.params.get('bb_std', 2.0)
        rsi_len = self.params.get('rsi_len', 14)
        
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
        bb = ta.bbands(df['close'], length=bb_len, std=bb_std)
        rsi = ta.rsi(df['close'], length=rsi_len)
        
        # Dynamic Column Finding
        # pandas_ta column names: BBL_20_2.0, BBM_20_2.0, BBU_20_2.0
        # But sometimes std is formatted differently.
        cols = bb.columns
        lower_col = [c for c in cols if c.startswith('BBL')][0]
        upper_col = [c for c in cols if c.startswith('BBU')][0]
        
        lower_band = bb[lower_col].values
        upper_band = bb[upper_col].values
        rsi_vals = rsi.values
        trend_vals = trend_series.values
        close_vals = df['close'].values
        
        position = np.zeros(len(df))
        curr_pos = 0
        
        for i in range(1, len(df)):
            trend_dir = trend_vals[i]
            
            if curr_pos == 0:
                # LONG: Bull Trend + Price touches Lower BB (Mean Reversion in Trend)
                if trend_dir == 1:
                    if close_vals[i] < lower_band[i] and rsi_vals[i] < 45:
                        curr_pos = 1
                        
                # SHORT: Bear Trend + Price touches Upper BB
                elif trend_dir == -1:
                    if close_vals[i] > upper_band[i] and rsi_vals[i] > 55:
                        curr_pos = -1
                    
            elif curr_pos == 1:
                # Exit Long: Price hits Upper BB or Trend Reverses
                if close_vals[i] > upper_band[i] or trend_dir == -1:
                    curr_pos = 0
            
            elif curr_pos == -1:
                # Exit Short: Price hits Lower BB or Trend Reverses
                if close_vals[i] < lower_band[i] or trend_dir == 1:
                    curr_pos = 0
            
            position[i] = curr_pos
            
        return pd.Series(position, index=df.index)
