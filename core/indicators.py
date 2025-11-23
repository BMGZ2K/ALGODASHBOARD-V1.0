import pandas as pd
import pandas_ta as ta
import numpy as np

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
    # Heikin Ashi Smoothing (Mathematically Precise)
    if USE_HEIKIN_ASHI:
        # HA Close = (Open + High + Low + Close) / 4
        df['ha_close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
        
        # HA Open = (Prev HA Open + Prev HA Close) / 2
        # Initialize first HA Open as the first raw Open (standard convention)
        ha_open = [df['open'].iloc[0]]
        
        # Iterate to calculate HA Open (Recursive dependency)
        # Optimization: Use values array for speed
        ha_close_values = df['ha_close'].values
        
        for i in range(1, len(df)):
            ha_open.append((ha_open[-1] + ha_close_values[i-1]) / 2)
            
        df['ha_open'] = ha_open
        
        # HA High = Max(High, HA Open, HA Close)
        df['ha_high'] = df[['high', 'ha_open', 'ha_close']].max(axis=1)
        
        # HA Low = Min(Low, HA Open, HA Close)
        df['ha_low'] = df[['low', 'ha_open', 'ha_close']].min(axis=1)
        
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
    df['rsi'] = rsi # Assign to DataFrame for later use
    rsi_value = rsi.iloc[-1] if not rsi.empty and not pd.isna(rsi.iloc[-1]) else 50.0 # Default to Neutral
    confirmed_rsi = rsi.iloc[-2] if len(rsi) > 1 and not pd.isna(rsi.iloc[-2]) else rsi_value
    
    # Smoothed RSI (Signal Noise Reduction)
    rsi_sma = ta.sma(rsi, length=3)
    rsi_smooth = rsi_sma.iloc[-1] if not rsi_sma.empty and not pd.isna(rsi_sma.iloc[-1]) else rsi_value
    
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
        confirmed_trend = st.iloc[-2][st_dir_col] if len(st) > 1 else current_trend
        if pd.isna(current_trend): current_trend = 0
        if pd.isna(confirmed_trend): confirmed_trend = 0
    else:
        current_trend = 0
        confirmed_trend = 0
    
    # SuperTrend (Slow)
    st_slow = ta.supertrend(calc_high, calc_low, calc_close, length=60, multiplier=3.0)
    if st_slow is not None and not st_slow.empty:
        st_slow_dir_col = [c for c in st_slow.columns if c.startswith('SUPERTd')][0]
        slow_trend = st_slow.iloc[-1][st_slow_dir_col]
        confirmed_slow_trend = st_slow.iloc[-2][st_slow_dir_col] if len(st_slow) > 1 else slow_trend
        if pd.isna(slow_trend): slow_trend = 0
        if pd.isna(confirmed_slow_trend): confirmed_slow_trend = 0
    else:
        slow_trend = 0
        confirmed_slow_trend = 0

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

    # EMA 200 (Major Trend Filter)
    df['ema_200'] = ta.ema(calc_close, length=200)
    ema_200 = df.iloc[-1]['ema_200'] if not pd.isna(df.iloc[-1]['ema_200']) else df.iloc[-1]['close']

    # Choppiness Index (CHOP) - Regime Filter
    # 100 * LOG10( SUM(ATR(1), n) / ( MaxHi(n) - MinLo(n) ) ) / LOG10(n)
    try:
        # Manual robust implementation
        # True Range for ATR(1)
        tr1 = ta.true_range(df['high'], df['low'], df['close'])
        sum_atr_n = tr1.rolling(14).sum()
        
        high_n = df['high'].rolling(14).max()
        low_n = df['low'].rolling(14).min()
        range_n = high_n - low_n
        
        # Safety: Avoid division by zero
        range_n = range_n.replace(0, 0.0000001)
        
        ratio = sum_atr_n / range_n
        # Safety: Avoid log10(0)
        ratio = ratio.replace(0, 0.0000001)
        
        chop_series = 100 * np.log10(ratio) / np.log10(14)
        current_chop = chop_series.iloc[-1] if not pd.isna(chop_series.iloc[-1]) else 50.0
        
    except Exception as e:
        # print(f"CHOP Error: {e}")
        current_chop = 50.0
    
    # Stochastic RSI (Standardized)
    rsi_series = rsi
    if rsi_series is not None:
        stoch_rsi_len = 14
        stoch_k_len = 3
        stoch_d_len = 3
        
        min_rsi = rsi_series.rolling(stoch_rsi_len).min()
        max_rsi = rsi_series.rolling(stoch_rsi_len).max()
        
        # Avoid division by zero
        denom = max_rsi - min_rsi
        denom = denom.replace(0, 0.000001)
        
        stoch = (rsi_series - min_rsi) / denom
        df['stoch_k'] = stoch.rolling(stoch_k_len).mean() * 100
        df['stoch_d'] = df['stoch_k'].rolling(stoch_d_len).mean()
        
        stoch_k = df.iloc[-1]['stoch_k'] if not pd.isna(df.iloc[-1]['stoch_k']) else 50.0
        stoch_d = df.iloc[-1]['stoch_d'] if not pd.isna(df.iloc[-1]['stoch_d']) else 50.0
        
        prev_stoch_k = df.iloc[-2]['stoch_k'] if len(df) > 1 and not pd.isna(df.iloc[-2]['stoch_k']) else stoch_k
        prev_stoch_d = df.iloc[-2]['stoch_d'] if len(df) > 1 and not pd.isna(df.iloc[-2]['stoch_d']) else stoch_d
    else:
        stoch_k, stoch_d, prev_stoch_k, prev_stoch_d = 50.0, 50.0, 50.0, 50.0

    # --- MARKET STRUCTURE & DIVERGENCE UTILS ---
    # Rolling Min/Max for Swing Stop Loss (10 periods)
    df['lowest_10'] = df['low'].rolling(10).min()
    df['highest_10'] = df['high'].rolling(10).max()
    
    lowest_10 = df.iloc[-1]['lowest_10']
    highest_10 = df.iloc[-1]['highest_10']
    
    # RSI Extremes for Divergence Check
    df['rsi_lowest_10'] = df['rsi'].rolling(10).min()
    df['rsi_highest_10'] = df['rsi'].rolling(10).max()
    
    rsi_lowest_10 = df.iloc[-1]['rsi_lowest_10']
    rsi_highest_10 = df.iloc[-1]['rsi_highest_10']

    # Handle NaNs in scalar returns
    if pd.isna(lower_bb): lower_bb = 0.0
    if pd.isna(upper_bb): upper_bb = 0.0
    if pd.isna(current_width): current_width = 0.0
    if pd.isna(width_threshold): width_threshold = 0.0

    return {
        'current_price': df.iloc[-1]['close'],
        'current_atr': current_atr,
        'rsi_value': rsi_value,
        'confirmed_rsi': confirmed_rsi,
        'current_adx': current_adx,
        'current_trend': current_trend,
        'confirmed_trend': confirmed_trend,
        'slow_trend': slow_trend,
        'confirmed_slow_trend': confirmed_slow_trend,
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
        'prev_adx': prev_adx,
        'confirmed_adx': prev_adx, # Alias for consistency
        'rsi_smooth': rsi_smooth,
        'ema_200': ema_200,
        'chop': current_chop,
        'lowest_10': lowest_10,
        'highest_10': highest_10,
        'rsi_lowest_10': rsi_lowest_10,
        'rsi_highest_10': rsi_highest_10
    }
