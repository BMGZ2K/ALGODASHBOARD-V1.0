from tools.wfo import Strategy
import pandas_ta as ta
import pandas as pd

class PullbackStrategy(Strategy):
    def generate_signals(self, df):
        # Params: ema_trend, rsi_length, rsi_buy, rsi_sell
        ema_trend_len = self.params.get('ema_trend', 200)
        rsi_len = self.params.get('rsi_len', 14)
        rsi_buy_lvl = self.params.get('rsi_buy', 40) # Buy if RSI < 40 in Uptrend
        rsi_sell_lvl = self.params.get('rsi_sell', 60) # Sell if RSI > 60 in Downtrend
        
        # Indicators
        df['ema_trend'] = ta.ema(df['close'], length=ema_trend_len)
        df['rsi'] = ta.rsi(df['close'], length=rsi_len)
        
        signals = pd.Series(0, index=df.index)
        
        # Logic:
        # Uptrend: Close > EMA Trend
        # Downtrend: Close < EMA Trend
        
        # Long: Uptrend + RSI < Buy Level
        long_cond = (df['close'] > df['ema_trend']) & (df['rsi'] < rsi_buy_lvl)
        
        # Short: Downtrend + RSI > Sell Level
        short_cond = (df['close'] < df['ema_trend']) & (df['rsi'] > rsi_sell_lvl)
        
        # Exit:
        # We can use RSI crossing 50 as exit
        exit_long = (df['rsi'] > 50)
        exit_short = (df['rsi'] < 50)
        
        # We need state management for exit in vectorized?
        # Simplified: Signal 1 enters/holds Long. Signal -1 enters/holds Short. Signal 0 is flat.
        # This is hard in pure vector without loop if exit condition is different from entry.
        
        # Let's use a simpler logic for vectorization:
        # Always Long if Uptrend AND RSI is "recovering" (e.g. RSI > 30)?
        # No, let's try:
        # Signal 1 when Long Cond met.
        # Signal 0 when Exit Long met.
        # Forward fill?
        
        # Let's try a pure condition:
        # 1 (Long) if Close > EMA
        # -1 (Short) if Close < EMA
        # But this is just Trend Following.
        
        # Let's try the Pullback logic precisely:
        # We use a loop for precision in signal generation (slower but correct).
        
        trend = df['close'] > df['ema_trend']
        rsi = df['rsi']
        
        position = 0
        sig_list = []
        
        for i in range(len(df)):
            if i < ema_trend_len:
                sig_list.append(0)
                continue
                
            current_trend_up = trend.iloc[i]
            current_rsi = rsi.iloc[i]
            
            if position == 0:
                if current_trend_up and current_rsi < rsi_buy_lvl:
                    position = 1
                elif not current_trend_up and current_rsi > rsi_sell_lvl:
                    position = -1
            elif position == 1:
                if current_rsi > 50 or not current_trend_up: # Exit on mean reversion or trend break
                    position = 0
            elif position == -1:
                if current_rsi < 50 or current_trend_up:
                    position = 0
            
            sig_list.append(position)
            
        return pd.Series(sig_list, index=df.index)
