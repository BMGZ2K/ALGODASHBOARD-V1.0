from tools.wfo import Strategy
import pandas_ta as ta
import pandas as pd
import numpy as np

class TrendPullbackStrategy(Strategy):
    def generate_signals(self, df):
        # Params: 
        # Trend (4h): st_len, st_mult
        # Entry (15m): rsi_len, rsi_buy
        # Risk: vol_target (daily %), lookback_vol
        
        st_len = self.params.get('st_len', 10)
        st_mult = self.params.get('st_mult', 3.0)
        rsi_len = self.params.get('rsi_len', 14)
        rsi_buy = self.params.get('rsi_buy', 40)
        
        # Dynamic Sizing Params
        use_vol_target = self.params.get('use_vol_target', False)
        target_vol_ann = self.params.get('target_vol', 0.40) # 40% annualized vol target
        
        # 1. Resample to 4h to get Trend
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
            
        agg_dict = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }
        
        df_4h = df.resample('4h').agg(agg_dict).dropna()
        st = ta.supertrend(df_4h['high'], df_4h['low'], df_4h['close'], length=st_len, multiplier=st_mult)
        
        st_dir_col = f"SUPERTd_{st_len}_{st_mult}"
        if st_dir_col not in st.columns:
             cols = [c for c in st.columns if c.startswith('SUPERTd')]
             if cols: st_dir_col = cols[0]
        
        df_4h['trend_dir'] = st[st_dir_col]
        trend_series = df_4h['trend_dir'].reindex(df.index).ffill()
        
        # 2. Calculate 15m Indicators
        rsi = ta.rsi(df['close'], length=rsi_len)
        
        # 3. Calculate Volatility for Sizing
        # Daily Volatility = std(returns) * sqrt(candles_per_day)
        # We use rolling std of pct_change
        returns = df['close'].pct_change()
        rolling_vol = returns.rolling(window=96).std() * np.sqrt(96) # 1 day window (96 * 15m)
        # Annualize: Daily * sqrt(365)
        annualized_vol = rolling_vol * np.sqrt(365)
        
        # Logic
        position = np.zeros(len(df))
        curr_pos = 0
        trend_vals = trend_series.values
        rsi_vals = rsi.values
        vol_vals = annualized_vol.values
        
        for i in range(1, len(df)):
            # Trend Filter
            is_uptrend = (trend_vals[i] == 1)
            
            # Sizing
            size = 1.0
            if use_vol_target and vol_vals[i] > 0:
                # Target Vol / Current Vol
                # Cap leverage at 2.0 to be safe
                raw_size = target_vol_ann / vol_vals[i]
                size = min(max(raw_size, 0.5), 2.0)
            
            if curr_pos == 0:
                if is_uptrend and rsi_vals[i] < rsi_buy:
                    curr_pos = size
                    
            elif curr_pos > 0: # In Long
                # Exit if Trend breaks OR RSI overbought
                if not is_uptrend:
                    curr_pos = 0
                elif rsi_vals[i] > 70:
                    curr_pos = 0
                else:
                    # Rebalance size? Usually we hold fixed size until exit to save fees.
                    # Let's keep the initial size for this trade.
                    # To do that effectively in vector loop, we need to store 'entry_size'
                    # But here curr_pos tracks state.
                    # If we want to update size dynamically:
                    if use_vol_target:
                         # Optional: Rebalance every bar? Too expensive.
                         # Keep same size.
                         pass
            
            position[i] = curr_pos
            
        return pd.Series(position, index=df.index)
