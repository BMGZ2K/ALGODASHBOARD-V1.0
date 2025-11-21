import pandas as pd
import pandas_ta as ta
import numpy as np
from itertools import product
from copy import deepcopy

class Strategy:
    def __init__(self, params):
        self.params = params
        
    def generate_signals(self, df):
        raise NotImplementedError("Should implement generate_signals")

class BacktestEngine:
    def __init__(self, initial_capital=10000, fee=0.0004, slippage=0.0002, leverage=1.0):
        self.initial_capital = initial_capital
        self.fee = fee # 0.04% Futures Taker Fee
        self.slippage = slippage # 0.02% Tight spread on ETH Futures
        self.leverage = leverage
        
    def run(self, df, strategy):
        signals = strategy.generate_signals(df.copy())
        
        df = df.copy()
        df['signal'] = signals
        
        # Shift signal by 1 to trade on next open
        df['position'] = df['signal'].shift(1).fillna(0)
        
        df['pct_change'] = df['close'].pct_change()
        
        # Strategy Return = Position * Market Change * Leverage
        df['strategy_return'] = df['position'] * df['pct_change'] * self.leverage
        
        # Trade Count: Entry (0->1) or Exit (1->0) or Flip (1->-1 implies 2 trades)
        df['trade_count'] = df['position'].diff().abs().fillna(0)
        
        # Cost is applied on NOTIONAL value (Capital * Leverage)
        # Total cost per turnover = (Fee + Slippage) * Leverage
        total_cost_pct = (self.fee + self.slippage) * self.leverage
        
        df['costs'] = df['trade_count'] * total_cost_pct
        
        df['net_return'] = df['strategy_return'] - df['costs']
        
        # Cumulative Return
        df['equity'] = self.initial_capital * (1 + df['net_return']).cumprod()
        
        return self.calculate_metrics(df)
    
    def calculate_metrics(self, df):
        total_return = (df['equity'].iloc[-1] / self.initial_capital) - 1
        
        # Win Rate
        winning_trades = df[df['net_return'] > 0]
        losing_trades = df[df['net_return'] < 0]
        win_rate = len(winning_trades) / (len(winning_trades) + len(losing_trades)) if (len(winning_trades) + len(losing_trades)) > 0 else 0
        
        # Drawdown
        rolling_max = df['equity'].cummax()
        drawdown = (df['equity'] - rolling_max) / rolling_max
        max_drawdown = drawdown.min()
        
        return {
            'total_return': total_return,
            'win_rate': win_rate,
            'max_drawdown': max_drawdown,
            'equity_curve': df['equity']
        }

class WFOOptimizer:
    def __init__(self, data_path, train_window_days=60, test_window_days=20):
        self.df = pd.read_csv(data_path)
        self.df['timestamp'] = pd.to_datetime(self.df['timestamp'])
        self.df.set_index('timestamp', inplace=True)
        self.train_window = pd.Timedelta(days=train_window_days)
        self.test_window = pd.Timedelta(days=test_window_days)
        
    def optimize(self, strategy_cls, param_grid, leverage=1.0):
        current_start = self.df.index.min()
        results = []
        
        print(f"Starting WFO for {strategy_cls.__name__} (Lev: {leverage}x)...")
        
        while True:
            train_end = current_start + self.train_window
            test_end = train_end + self.test_window
            
            if test_end > self.df.index.max():
                break
                
            train_data = self.df[current_start:train_end]
            test_data = self.df[train_end:test_end]
            
            if len(train_data) < 100 or len(test_data) < 10:
                current_start += self.test_window
                continue
            
            # Optimization Step
            best_params = None
            best_score = -np.inf
            
            # Grid Search
            keys, values = zip(*param_grid.items())
            combinations = [dict(zip(keys, v)) for v in product(*values)]
            
            for params in combinations:
                strat = strategy_cls(params)
                # ML Support: Train if method exists
                if hasattr(strat, 'train'):
                    strat.train(train_data)
                    
                engine = BacktestEngine(leverage=leverage)
                metrics = engine.run(train_data, strat)
                
                # Optimization Goal: Maximize Return / Abs(MaxDrawdown)
                score = metrics['total_return']
                if metrics['max_drawdown'] != 0:
                     score = metrics['total_return'] / abs(metrics['max_drawdown'])
                
                if score > best_score:
                    best_score = score
                    best_params = params
            
            # Out-of-Sample Test
            best_strat = strategy_cls(best_params)
            # ML Support: Re-train best model on Train Data before testing on Test Data
            if hasattr(best_strat, 'train'):
                best_strat.train(train_data)
                
            test_engine = BacktestEngine(leverage=leverage)
            test_metrics = test_engine.run(test_data, best_strat)
            
            # Calculate Buy & Hold Return for this period (Unleveraged Benchmark)
            bnh_return = (test_data['close'].iloc[-1] / test_data['close'].iloc[0]) - 1
            
            results.append({
                'period_start': train_end,
                'period_end': test_end,
                'params': best_params,
                'return': test_metrics['total_return'],
                'drawdown': test_metrics['max_drawdown'],
                'bnh_return': bnh_return
            })
            
            current_start += self.test_window
            
        return results
