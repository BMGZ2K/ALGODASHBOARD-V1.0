from strategies.trend_following import TrendFollowingStrategy
import pandas_ta as ta
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier

class MetaMLStrategy(TrendFollowingStrategy):
    def __init__(self, params):
        super().__init__(params)
        self.model = None
        self.meta_features = ['adx', 'rsi', 'volatility', 'ema_spread']
        
    def prepare_meta_features(self, df):
        df = df.copy()
        # Base Indicators
        fast = self.params.get('fast_ema', 50)
        slow = self.params.get('slow_ema', 200)
        
        df['ema_fast'] = ta.ema(df['close'], length=fast)
        df['ema_slow'] = ta.ema(df['close'], length=slow)
        
        # Meta Features (Context)
        df['adx'] = ta.adx(df['high'], df['low'], df['close'], length=14)['ADX_14']
        df['rsi'] = ta.rsi(df['close'], length=14) / 100.0
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        df['volatility'] = df['atr'] / df['close']
        df['ema_spread'] = (df['ema_fast'] - df['ema_slow']) / df['close']
        
        return df

    def train(self, train_df):
        # 1. Generate Base Signals
        # We need to know what the base strategy WOULD have done.
        # But the base strategy is "Always In". 
        # Let's look at transitions or state.
        
        df = self.prepare_meta_features(train_df).dropna()
        
        # Generate Labels
        # If EMA Fast > EMA Slow (Long State), was it profitable?
        # We look at Next Period Return.
        # If Long and Return > 0 -> Label 1
        # If Short and Return < 0 -> Label 1
        # Else 0
        
        # Future Return
        df['ret_next'] = df['close'].pct_change().shift(-1)
        
        # Base Signal State
        df['base_signal'] = np.where(df['ema_fast'] > df['ema_slow'], 1, -1)
        
        # Labeling
        # Valid Trade: (Signal 1 AND Ret > 0) OR (Signal -1 AND Ret < 0)
        conditions = [
            (df['base_signal'] == 1) & (df['ret_next'] > 0),
            (df['base_signal'] == -1) & (df['ret_next'] < 0)
        ]
        df['target'] = np.select(conditions, [1, 1], default=0)
        
        # Train
        X = df[self.meta_features]
        y = df['target']
        
        n_est = self.params.get('n_estimators', 100)
        depth = self.params.get('max_depth', 5)
        
        self.model = RandomForestClassifier(n_estimators=n_est, max_depth=depth, random_state=42)
        self.model.fit(X, y)

    def generate_signals(self, df):
        # 1. Get Base Signals logic (re-implemented here to match features)
        df = self.prepare_meta_features(df)
        
        # Valid rows must have no NaNs in required columns
        cols_to_check = self.meta_features + ['ema_fast', 'ema_slow']
        valid_mask = df[cols_to_check].notna().all(axis=1)
        valid_indices = df.index[valid_mask]
        
        if self.model is None or len(valid_indices) == 0:
            return pd.Series(0, index=df.index)
            
        # Filter df to valid only
        df_valid = df.loc[valid_indices]
        
        # Base Logic
        base_signal = np.where(df_valid['ema_fast'] > df_valid['ema_slow'], 1, -1)
        
        # Meta Logic
        X_test = df_valid[self.meta_features]
        probs = self.model.predict_proba(X_test)[:, 1] # Prob of "Success"
        
        threshold = self.params.get('threshold', 0.55)
        
        # Final Signal
        final_signal = np.where(probs > threshold, base_signal, 0)
        
        signals = pd.Series(0, index=df.index)
        signals.loc[valid_indices] = final_signal
        
        return signals

