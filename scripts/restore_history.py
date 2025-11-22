import pandas as pd
import os

def restore_logs():
    # Paths
    old_trades_path = "backups/ALGODASHBOARD-V1.0-main/trades_log.csv"
    new_trades_path = "logs/trades_log.csv"
    
    old_balance_path = "backups/ALGODASHBOARD-V1.0-main/balance_history.csv"
    new_balance_path = "logs/balance_history.csv"
    
    print("Restoring Trade History...")
    if os.path.exists(old_trades_path) and os.path.exists(new_trades_path):
        try:
            df_old = pd.read_csv(old_trades_path)
            df_new = pd.read_csv(new_trades_path)
            
            # Concatenate: Old then New
            df_combined = pd.concat([df_old, df_new], ignore_index=True)
            
            # Remove duplicates just in case (based on timestamp and symbol)
            df_combined.drop_duplicates(subset=['timestamp', 'symbol', 'amount'], keep='last', inplace=True)
            
            # Sort by timestamp
            df_combined['timestamp'] = pd.to_datetime(df_combined['timestamp'], format='mixed')
            df_combined.sort_values('timestamp', inplace=True)
            
            # Save back
            df_combined.to_csv(new_trades_path, index=False)
            print(f"✅ Merged {len(df_old)} old trades with {len(df_new)} new trades. Total: {len(df_combined)}")
        except Exception as e:
            print(f"❌ Error merging trades: {e}")
    else:
        print("⚠️ Trade log files not found for merge.")

    print("\nRestoring Balance History...")
    if os.path.exists(old_balance_path) and os.path.exists(new_balance_path):
        try:
            df_old = pd.read_csv(old_balance_path)
            df_new = pd.read_csv(new_balance_path)
            
            df_combined = pd.concat([df_old, df_new], ignore_index=True)
            df_combined.drop_duplicates(subset=['timestamp'], keep='last', inplace=True)
            
            df_combined['timestamp'] = pd.to_datetime(df_combined['timestamp'], format='mixed')
            df_combined.sort_values('timestamp', inplace=True)
            
            df_combined.to_csv(new_balance_path, index=False)
            print(f"✅ Merged {len(df_old)} old balance records with {len(df_new)} new records. Total: {len(df_combined)}")
        except Exception as e:
            print(f"❌ Error merging balance history: {e}")
    else:
        print("⚠️ Balance history files not found for merge.")

if __name__ == "__main__":
    restore_logs()
