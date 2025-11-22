import unittest
import os
import sys
from unittest.mock import MagicMock, patch

# Add current directory to path so we can import run_live
sys.path.append(os.getcwd())

import run_live

class TestTradingBot(unittest.TestCase):

    def test_load_strategy_config_default(self):
        """Test that default config is returned if file doesn't exist"""
        config = run_live.load_strategy_config("non_existent_strategy")
        self.assertIn('st_len', config)
        self.assertIn('rsi_len', config)
        self.assertEqual(config['st_len'], 10)

    def test_load_strategy_config_existing(self):
        """Test loading an existing strategy config"""
        # Create a dummy config file
        strategy_name = "test_strategy"
        os.makedirs("best_strategies", exist_ok=True)
        with open(f"best_strategies/{strategy_name}_config.txt", "w") as f:
            f.write("{'st_len': 20, 'st_mult': 4.0}")
        
        config = run_live.load_strategy_config(strategy_name)
        self.assertEqual(config['st_len'], 20)
        self.assertEqual(config['st_mult'], 4.0)
        
        # Cleanup
        os.remove(f"best_strategies/{strategy_name}_config.txt")

    @patch('run_live.ccxt.binance')
    def test_get_exchange(self, mock_binance):
        """Test exchange initialization"""
        exchange = run_live.get_exchange()
        self.assertIsNotNone(exchange)
        # Verify that binance was called
        mock_binance.assert_called()

    def test_log_trade(self):
        """Test logging a trade"""
        test_log_file = "test_trades_log.csv"
        # Temporarily overwrite LOG_FILE in run_live
        original_log_file = run_live.LOG_FILE
        run_live.LOG_FILE = test_log_file
        
        try:
            if os.path.exists(test_log_file):
                os.remove(test_log_file)
                
            run_live.log_trade("2023-01-01", "ETH/USDT", "buy", 1.0, 2000.0, "Test", "FILLED")
            
            self.assertTrue(os.path.exists(test_log_file))
            with open(test_log_file, 'r') as f:
                content = f.read()
                self.assertIn("ETH/USDT", content)
                self.assertIn("FILLED", content)
        finally:
            run_live.LOG_FILE = original_log_file
            if os.path.exists(test_log_file):
                os.remove(test_log_file)

if __name__ == '__main__':
    unittest.main()
