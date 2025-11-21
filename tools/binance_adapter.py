import ccxt

class BinanceDemoAdapter(ccxt.binance):
    """
    A specialized CCXT wrapper for the Binance Futures Testnet (Demo).
    It handles URL overrides, method suppressions (to avoid invalid endpoints),
    and raw API calls required for the Demo environment.
    """
    
    def __init__(self, config):
        # Force specific options for Demo compatibility
        config['options'] = config.get('options', {})
        config['options'].update({
            'defaultType': 'future',
            'adjustForTimeDifference': True,
            'warnOnFetchOpenOrdersWithoutSymbol': False,
            'fetchBalance': {'type': 'future'},
            'defaultMarginMode': 'isolated',
        })
        
        super().__init__(config)
        
        # 1. URL Overrides for Demo FAPI
        self.urls['api'] = {
            'fapiPublic': 'https://demo-fapi.binance.com/fapi/v1',
            'fapiPrivate': 'https://demo-fapi.binance.com/fapi/v1',
            'public': 'https://demo-fapi.binance.com/fapi/v1',
            'private': 'https://demo-fapi.binance.com/fapi/v1',
            # Redirect SAPI to FAPI to minimize 404s on internal checks
            'sapi': 'https://demo-fapi.binance.com/fapi/v1',
        }
        
        # 2. Capability Overrides (Prevent calls to non-existent endpoints)
        self.has['fetchCurrencies'] = False
        self.has['fetchMarginMode'] = False
        self.has['setMarginMode'] = False
        self.has['fetchMarginModes'] = False
        
        # 3. Manual Market Definition (Fallback)
        # This prevents load_markets() from failing if it tries to hit margin endpoints
        self.markets = {
            'ETH/USDT': {
                'id': 'ETHUSDT',
                'symbol': 'ETH/USDT',
                'base': 'ETH',
                'quote': 'USDT',
                'baseId': 'ETH',
                'quoteId': 'USDT',
                'active': True,
                'precision': {'amount': 3, 'price': 2},
                'limits': {'amount': {'min': 0.001, 'max': 10000}},
                'type': 'future',
                'spot': False,
                'future': True,
                'contract': True,
                'option': False,
                'linear': True,
                'info': {}
            }
        }
        self.markets_by_id = {'ETHUSDT': self.markets['ETH/USDT']}
        self.ids = ['ETHUSDT']
        self.symbols = ['ETH/USDT']

    def fetch_margin_modes(self, symbols=None, params={}):
        # No-op to prevent API error
        return None

    def fetch_real_balance(self):
        """
        Fetches balance using the V2 endpoint via a raw request, 
        bypassing standard CCXT logic that might fail on Demo.
        """
        try:
            # Use relative path traversal to reach v2
            raw_account = self.request('../v2/account', api='fapiPrivate', method='GET')
            return {
                'usdt': float(raw_account['totalWalletBalance']),
                'positions': raw_account['positions']
            }
        except Exception as e:
            # Fallback to standard if relative path fails (unlikely)
            print(f"   ⚠️ V2 Balance Fetch Error: {e}")
            return {'usdt': 0.0, 'positions': []}

    def set_leverage_raw(self, symbol, leverage):
        """
        Sets leverage using raw API call to avoid CCXT's internal margin checks.
        """
        try:
            self.fapiPrivatePostLeverage({
                'symbol': symbol.replace('/', ''),
                'leverage': leverage
            })
            return True
        except Exception as e:
            print(f"   ⚠️ Set Leverage Error: {e}")
            return False

    def set_mode_oneway(self):
        """
        Forces One-Way Position Mode (Hedge Mode causes -4061 error).
        """
        try:
            self.fapiPrivatePostPositionSideDual({'dualSidePosition': 'false'})
            return True
        except Exception as e:
            if "-4059" in str(e): # No need to change
                return True
            print(f"   ℹ️  Position Mode Update: {e}")
            return False

    def create_order_raw(self, symbol, side, type, quantity, price=None):
        """
        Sends a raw order to bypass client-side validation.
        """
        params = {
            'symbol': symbol.replace('/', ''),
            'side': side.upper(),
            'type': type.upper(),
            'quantity': "{:.3f}".format(quantity),
        }
        if price and type.upper() == 'LIMIT':
            params['price'] = "{:.2f}".format(price)
            params['timeInForce'] = 'GTC'
            
        return self.fapiPrivatePostOrder(params)

    def create_smart_order(self, symbol, side, quantity, current_price):
        """
        Smart Execution: Tries to place a LIMIT order slightly better than market to be a Maker.
        In this simplified polling version, we just place a Market order for guaranteed execution
        because managing open Limit orders without Websockets is risky (price moves away).
        
        Evolution: In future, we can add 'PostOnly' or 'Limit Chase'.
        For now, we stick to Market but structured for easy upgrade.
        """
        # TODO: Implement Limit Chase logic
        return self.create_order_raw(symbol, side, 'MARKET', quantity)
