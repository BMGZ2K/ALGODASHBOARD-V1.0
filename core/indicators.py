import pandas as pd
import pandas_ta as ta

def calculate_indicators(df, params):
    """
    Calculates technical indicators using pandas_ta.
    Returns a dictionary of the latest indicator values and the processed DataFrame.
    """
    # --- SMART CONFIG ---
    USE_HEIKIN_ASHI = True
    
    # --- DONCHIAN CHANNEL (Trend Filter) ---
    window = params.get('breakout_window', 20)
    df['donchian_high'] = df['high'].rolling(window=window).max()
    df['donchian_low'] = df['low'].rolling(window=window).min()
    
    donchian_high = df['donchian_high'].iloc[-2] # Previous candle to avoid lookahead
    donchian_low = df['donchian_low'].iloc[-2]
    
    # --- DATA PREPARATION ---
    # Heikin Ashi Smoothing
    if USE_HEIKIN_ASHI:
        df['ha_close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
        # Initialize ha_open with open
        df['ha_open'] = df['open']
        # Vectorized approximation for speed:
        df['ha_open'] = (df['open'].shift(1) + df['close'].shift(1)) / 2
        df.loc[df.index[0], 'ha_open'] = df['open'].iloc[0] # Fix first NaN using .loc
        
        df['ha_high'] = df[['high', 'open', 'close']].max(axis=1)
        df['ha_low'] = df[['low', 'open', 'close']].min(axis=1)
        
        # Use HA values for indicators
        calc_high, calc_low, calc_close = df['ha_high'], df['ha_low'], df['ha_close']
    else:
        calc_high, calc_low, calc_close = df['high'], df['low'], df['close']

    # --- INDICATORS (Using Smoothed or Raw) ---
    # ATR (Always use raw for true volatility)
    atr = ta.atr(df['high'], df['low'], df['close'], length=14)
    current_atr = atr.iloc[-1] if not atr.empty and not pd.isna(atr.iloc[-1]) else 0.0
    
    # RSI
    rsi = ta.rsi(calc_close, length=14)
    rsi_value = rsi.iloc[-1] if not rsi.empty and not pd.isna(rsi.iloc[-1]) else 50.0 # Default to Neutral
    
    # ADX
    adx = ta.adx(calc_high, calc_low, calc_close, length=14)
    if adx is not None and not adx.empty:
        adx_col = [c for c in adx.columns if c.startswith('ADX')][0]
        current_adx = adx.iloc[-1][adx_col]
        prev_adx = adx.iloc[-2][adx_col] if len(adx) > 1 else current_adx
        
        if pd.isna(current_adx): current_adx = 0.0
        if pd.isna(prev_adx): prev_adx = 0.0
    else:
        current_adx = 0.0
        prev_adx = 0.0
    
    # SuperTrend (Fast)
    st = ta.supertrend(calc_high, calc_low, calc_close, length=10, multiplier=1.5)
    if st is not None and not st.empty:
        st_dir_col = [c for c in st.columns if c.startswith('SUPERTd')][0]
        current_trend = st.iloc[-1][st_dir_col]
        if pd.isna(current_trend): current_trend = 0
    else:
        current_trend = 0
    
    # SuperTrend (Slow)
    st_slow = ta.supertrend(calc_high, calc_low, calc_close, length=60, multiplier=3.0)
    if st_slow is not None and not st_slow.empty:
        st_slow_dir_col = [c for c in st_slow.columns if c.startswith('SUPERTd')][0]
        slow_trend = st_slow.iloc[-1][st_slow_dir_col]
        if pd.isna(slow_trend): slow_trend = 0
    else:
        slow_trend = 0

    # Bollinger Bands & Squeeze
    bb = ta.bbands(calc_close, length=20, std=2.0)
    if bb is not None and not bb.empty:
        lower_col = [c for c in bb.columns if c.startswith('BBL')][0]
        upper_col = [c for c in bb.columns if c.startswith('BBU')][0]
        lower_bb = bb.iloc[-1][lower_col]
        upper_bb = bb.iloc[-1][upper_col]
        
        # Squeeze Metrics
        df['bb_width'] = (bb[upper_col] - bb[lower_col]) / calc_close
        df['bb_w_sma'] = ta.sma(df['bb_width'], length=20)
        current_width = df.iloc[-1]['bb_width']
        width_threshold = df.iloc[-1]['bb_w_sma']
    else:
        lower_bb, upper_bb, current_width, width_threshold = 0.0, 0.0, 0.0, 0.0
    
    # Volume SMA
    df['vol_sma'] = ta.sma(df['volume'], length=20)
    current_vol = df.iloc[-1]['volume']
    vol_sma = df.iloc[-1]['vol_sma'] if not pd.isna(df.iloc[-1]['vol_sma']) else current_vol
    
    # Stochastic RSI
    rsi_series = rsi
    if rsi_series is not None:
        min_rsi = rsi_series.rolling(14).min()
        max_rsi = rsi_series.rolling(14).max()
        stoch = (rsi_series - min_rsi) / (max_rsi - min_rsi)
        df['stoch_k'] = stoch.rolling(3).mean() * 100
        df['stoch_d'] = df['stoch_k'].rolling(3).mean()
        stoch_k = df.iloc[-1]['stoch_k'] if not pd.isna(df.iloc[-1]['stoch_k']) else 50.0
        stoch_d = df.iloc[-1]['stoch_d'] if not pd.isna(df.iloc[-1]['stoch_d']) else 50.0
        prev_stoch_k = df.iloc[-2]['stoch_k'] if len(df) > 1 and not pd.isna(df.iloc[-2]['stoch_k']) else 50.0
        prev_stoch_d = df.iloc[-2]['stoch_d'] if len(df) > 1 and not pd.isna(df.iloc[-2]['stoch_d']) else 50.0
    else:
        stoch_k, stoch_d, prev_stoch_k, prev_stoch_d = 50.0, 50.0, 50.0, 50.0

    # Handle NaNs in scalar returns
    if pd.isna(lower_bb): lower_bb = 0.0
    if pd.isna(upper_bb): upper_bb = 0.0
    if pd.isna(current_width): current_width = 0.0
    if pd.isna(width_threshold): width_threshold = 0.0

    return {
        'current_price': df.iloc[-1]['close'],
        'current_atr': current_atr,
        'rsi_value': rsi_value,
        'current_adx': current_adx,
        'current_trend': current_trend,
        'slow_trend': slow_trend,
        'lower_bb': lower_bb,
        'upper_bb': upper_bb,
        'current_width': current_width,
        'width_threshold': width_threshold,
        'current_vol': current_vol,
        'vol_sma': vol_sma,
        'stoch_k': stoch_k,
        'stoch_d': stoch_d,
        'prev_stoch_k': prev_stoch_k,
        'prev_stoch_d': prev_stoch_d,
        'donchian_high': donchian_high,
        'donchian_low': donchian_low,
        'prev_adx': prev_adx
    }
