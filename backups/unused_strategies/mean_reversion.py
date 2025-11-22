from tools.wfo import Strategy
import pandas_ta as ta
import pandas as pd

class MeanReversionStrategy(Strategy):
    def generate_signals(self, df):
        # Params: bb_length, bb_std
        length = self.params.get('bb_length', 20)
        std = self.params.get('bb_std', 2.0)
        
        # Indicators
        bb = ta.bbands(df['close'], length=length, std=std)
        # Returns columns like BBL_20_2.0, BBM_20_2.0, BBU_20_2.0
        # Column names depend on pandas_ta version, usually:
        # BBL_{length}_{std}, BBM_..., BBU_...
        
        lower_col = f"BBL_{length}_{std}"
        upper_col = f"BBU_{length}_{std}"
        
        if lower_col not in bb.columns:
             # Fallback or check columns
             lower_col = bb.columns[0]
             upper_col = bb.columns[2]
        
        df = pd.concat([df, bb], axis=1)
        
        signals = pd.Series(0, index=df.index)
        
        # Logic
        # Buy when price < lower band
        # Sell when price > upper band
        
        # We use a stateful approach here to hold until mean.
        # Since generate_signals returns a series for the vector backtester, 
        # we might need a loop or a smart fill.
        # Vectorized simple mean reversion:
        
        long_cond = df['close'] < df[lower_col]
        short_cond = df['close'] > df[upper_col]
        
        signals[long_cond] = 1
        signals[short_cond] = -1
        
        # If 0, we want to close if we cross mean? 
        # Or hold? 
        # Simple version: always in market or out. 
        # Let's forward fill the signal to hold until opposite signal?
        # No, Mean Reversion usually exits at Mean.
        # Let's keep it simple: Signal 1 (Long), -1 (Short), 0 (Neutral).
        
        return signals
