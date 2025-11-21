from tools.wfo import Strategy
import pandas_ta as ta
import pandas as pd

class BreakoutStrategy(Strategy):
    def generate_signals(self, df):
        # Params: window, adx_threshold
        window = self.params.get('window', 20)
        adx_threshold = self.params.get('adx_threshold', 20)
        
        # Indicators
        # Donchian Channel (Rolling Max/Min)
        # We need previous N highs/lows (excluding current to avoid lookahead bias if using High/Low of current)
        # But typically breakout is: if Current Price > Max(Previous N Highs)
        
        df['high_max'] = df['high'].rolling(window=window).max().shift(1)
        df['low_min'] = df['low'].rolling(window=window).min().shift(1)
        
        # ADX
        adx = ta.adx(df['high'], df['low'], df['close'], length=14)
        # adx returns ADX_14, DMP_14, DMN_14. We need ADX_14
        adx_col = f"ADX_14"
        if adx_col not in adx.columns:
            adx_col = adx.columns[0]
        
        df = pd.concat([df, adx], axis=1)
        
        signals = pd.Series(0, index=df.index)
        
        # Logic
        # Long: Close > High Max AND ADX > Threshold
        long_cond = (df['close'] > df['high_max']) & (df[adx_col] > adx_threshold)
        
        # Short: Close < Low Min AND ADX > Threshold
        short_cond = (df['close'] < df['low_min']) & (df[adx_col] > adx_threshold)
        
        signals[long_cond] = 1
        signals[short_cond] = -1
        
        # This is a "Stop and Reverse" system if we don't have a specific exit.
        # But breakouts often fail. A trailing stop is ideal.
        # For vector testing, let's assume we flip.
        
        return signals
