from tools.wfo import Strategy
import pandas_ta as ta
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier

class MLStrategy(Strategy):
    def __init__(self, params):
        super().__init__(params)
        self.model = None
        self.feature_cols = ['rsi_norm', 'ema_slope', 'volatility', 'price_dist_ema']
        
    def prepare_features(self, df):
        df = df.copy()
        # Features
        df['rsi'] = ta.rsi(df['close'], length=14)
        df['ema_50'] = ta.ema(df['close'], length=50)
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        
        # Normalized / Stationary Features
        df['rsi_norm'] = df['rsi'] / 100.0
        # Slope of EMA (Change over last 3 bars)
        df['ema_slope'] = df['ema_50'].diff(3) / df['ema_50']
        # Volatility
        df['volatility'] = df['atr'] / df['close']
        # Price distance from EMA
        df['price_dist_ema'] = (df['close'] - df['ema_50']) / df['ema_50']
        
        # Target: 1 if Next Close > Current Close, else 0
        # But for trading, let's try: 1 if Next Return > threshold (e.g. 0.1%)
        # Or simpler: Direction
        df['target'] = (df['close'].shift(-1) > df['close']).astype(int)
        
        return df.dropna()

    def train(self, train_df):
        # Prepare data
        data = self.prepare_features(train_df)
        
        if len(data) < 50:
            return # Not enough data
            
        X = data[self.feature_cols]
        y = data['target']
        
        # Hyperparams
        n_est = self.params.get('n_estimators', 50)
        depth = self.params.get('max_depth', 5)
        
        self.model = RandomForestClassifier(n_estimators=n_est, max_depth=depth, random_state=42)
        self.model.fit(X, y)
        
    def generate_signals(self, df):
        if self.model is None:
            return pd.Series(0, index=df.index)
            
        data = self.prepare_features(df)
        valid_indices = data.index
        
        if len(valid_indices) == 0:
            return pd.Series(0, index=df.index)
            
        X_test = data[self.feature_cols]
        
        # Predict Probabilities
        probs = self.model.predict_proba(X_test)
        # probs is [n_samples, 2] (class 0, class 1)
        
        # Logic: Only Long if Prob(Up) > Threshold
        # Only Short if Prob(Down) > Threshold
        threshold = self.params.get('threshold', 0.55)
        
        # Class 1 is Up (Index 1)
        prob_up = probs[:, 1]
        prob_down = probs[:, 0]
        
        signals_values = np.zeros(len(X_test))
        
        # Vectorized logic
        signals_values[prob_up > threshold] = 1
        signals_values[prob_down > threshold] = -1
        
        # Map back
        signals = pd.Series(0, index=df.index)
        signals.loc[valid_indices] = signals_values
        
        return signals

