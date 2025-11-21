import sys
import os
import pandas as pd
import numpy as np
from tools.wfo import WFOOptimizer
from strategies.trend_following import TrendFollowingStrategy
from strategies.ml_strategy import MLStrategy
from strategies.meta_strategy import MetaMLStrategy
from strategies.rsi_2 import RSI2Strategy
from strategies.supertrend import SuperTrendStrategy
from strategies.trend_pullback import TrendPullbackStrategy
from strategies.hybrid import HybridStrategy
from strategies.smart_hybrid import SmartHybridStrategy
from strategies.bollinger_hybrid import BollingerHybridStrategy

def analyze_results(results, strategy_name):
    if not results:
        print(f"No results for {strategy_name}")
        return None

    df = pd.DataFrame(results)
    total_return = (1 + df['return']).prod() - 1
    avg_dd = df['drawdown'].mean()
    
    print(f"\n--- Results for {strategy_name} ---")
    print(f"Total Cumulative Return: {total_return:.2%}")
    print(f"Average Drawdown: {avg_dd:.2%}")
    
    # Save best params
    best_period = df.loc[df['return'].idxmax()]
    print(f"Best Single Period Return: {best_period['return']:.2%} with params {best_period['params']}")
    
    # Save to CSV
    df.to_csv(f"results/{strategy_name}_wfo_results.csv", index=False)
    
    # Save best strategy config
    with open(f"best_strategies/{strategy_name}_config.txt", "w") as f:
        f.write(str(best_period['params']))
        
    return total_return

def main():
    # Switch to 5m data for High Frequency WFO
    data_file = 'data/ETHUSDT_5m.csv'
    if not os.path.exists(data_file):
        print(f"Data file {data_file} not found. Run downloader first.")
        return

    print(f"Loading data from {data_file}...")
    
    # WFO Settings
    # Shorter windows for 5m data (30 days train, 5 days test)
    optimizer = WFOOptimizer(data_file, train_window_days=20, test_window_days=5)
    
    # 1. Baseline: Hybrid Strategy
    print("\n>>> BENCHMARKING: Hybrid Strategy (Baseline)")
    hybrid_params = {
        'st_len': [10],
        'st_mult': [3.0],
        'rsi_len': [14],
        'rsi_buy': [40],
        'breakout_window': [96] 
    }
    ret_hybrid = analyze_results(optimizer.optimize(HybridStrategy, hybrid_params, leverage=2.0), "Hybrid_Futures_2x_LongShort")
    
    # 2. Challenger 1: Smart Hybrid (ATR TP + Scalping)
    print("\n>>> BENCHMARKING: Smart Hybrid Strategy (Challenger 1)")
    smart_params = {
        'st_len': [10, 14],
        'st_mult': [1.5, 2.0, 3.0], # Lower mult = more trades
        'rsi_len': [14],
        'rsi_buy': [30, 40, 50], # Higher buy = earlier entry
        'atr_len': [14],
        'tp_mult': [1.5, 2.0, 3.0] # Tighter TP
    }
    ret_smart = analyze_results(optimizer.optimize(SmartHybridStrategy, smart_params, leverage=2.0), "Smart_Hybrid_Futures_2x_LongShort")

    # 3. Challenger 2: Bollinger Hybrid
    print("\n>>> BENCHMARKING: Bollinger Hybrid Strategy (Challenger 2)")
    bb_params = {
        'st_len': [10],
        'st_mult': [3.0],
        'bb_len': [20],
        'bb_std': [2.0, 2.5],
        'rsi_len': [14]
    }
    ret_bb = analyze_results(optimizer.optimize(BollingerHybridStrategy, bb_params, leverage=2.0), "Bollinger_Hybrid_Futures_2x")
    
    print("\n" + "="*40)
    print("CHAMPIONSHIP RESULT")
    print("="*40)
    print(f"Hybrid (Baseline): {ret_hybrid:.2%}")
    print(f"Smart Hybrid (Challenger 1): {ret_smart:.2%}")
    print(f"Bollinger Hybrid (Challenger 2): {ret_bb:.2%}")
    
    best_ret = max(ret_hybrid, ret_smart, ret_bb)
    
    if best_ret == ret_bb:
        print("🏆 NEW CHAMPION: Bollinger Hybrid! Updating config...")
    elif best_ret == ret_smart:
        print("🏆 NEW CHAMPION: Smart Hybrid! Updating config...")
    else:
        print("🛡️  BASELINE DEFENDED: Hybrid remains the best.")

if __name__ == "__main__":
    main()
