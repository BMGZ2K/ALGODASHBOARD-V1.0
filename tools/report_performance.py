import pandas as pd
import os

LOG_FILE = "trades_log.csv"

def report():
    if not os.path.exists(LOG_FILE):
        print("No trade log found yet.")
        return

    df = pd.read_csv(LOG_FILE)
    print(f"\n--- Performance Report ---")
    print(f"Total Trades: {len(df)}")
    
    if len(df) == 0: return

    # Filter Success trades
    filled = df[df['status'] == 'FILLED'].copy()
    print(f"Filled Orders: {len(filled)}")
    
    if len(filled) == 0: return
    
    # Simple PnL estimation (FIFO logic is complex, this is raw volume analysis)
    # Buy Volume vs Sell Volume
    
    buys = filled[filled['side'] == 'buy']
    sells = filled[filled['side'] == 'sell']
    
    buy_vol = (buys['amount'] * buys['price']).sum()
    sell_vol = (sells['amount'] * sells['price']).sum()
    
    # Net ETH Position
    net_eth = buys['amount'].sum() - sells['amount'].sum()
    
    print(f"Total Buy Volume: ${buy_vol:.2f}")
    print(f"Total Sell Volume: ${sell_vol:.2f}")
    print(f"Net Position (Inventory): {net_eth:.4f} ETH")
    
    # Realized PnL is hard to calc without closed loop, but we can show activity
    print("\nRecent Activity:")
    print(filled[['timestamp', 'side', 'amount', 'price', 'reason']].tail(5))

if __name__ == "__main__":
    report()
