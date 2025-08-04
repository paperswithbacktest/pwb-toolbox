from tests.stubs import pd
import sys
import types


def test_execute_orders_reconnects_on_disconnect():
    sys.modules['pandas'] = pd
    pd.Timestamp.utcnow = lambda: pd.Timestamp('2020-01-01')
    sys.modules['matplotlib'] = types.ModuleType('matplotlib')
    sys.modules['matplotlib.pyplot'] = types.SimpleNamespace()
    np_mod = types.ModuleType('numpy')
    np_mod.exceptions = types.SimpleNamespace(VisibleDeprecationWarning=Warning)
    np_mod.VisibleDeprecationWarning = Warning
    sys.modules['numpy'] = np_mod
    sci = types.ModuleType('scipy')
    sci.integrate = types.SimpleNamespace(odeint=lambda *args, **kwargs: [])
    sys.modules['scipy'] = sci
    sys.modules['scipy.integrate'] = sci.integrate

    class DummyIB:
        def __init__(self):
            self.connected = False
            self.connect_calls = 0
            self.place_order_calls = 0

        def connect(self, host='127.0.0.1', port=7497, clientId=1):
            self.connected = True
            self.connect_calls += 1
            self.host = host
            self.port = port
            self.clientId = clientId

        def disconnect(self):
            self.connected = False

        def isConnected(self):
            return self.connected

        def reqMarketDataType(self, *args, **kwargs):
            pass

        def qualifyContracts(self, contract):
            pass

        def placeOrder(self, contract, order):
            self.place_order_calls += 1
            if self.place_order_calls == 1:
                self.connected = False
                raise ConnectionError('disconnected')
            return types.SimpleNamespace(
                order=types.SimpleNamespace(orderId=1, orderType=order.orderType),
                orderStatus=types.SimpleNamespace(status='Filled', filled=1, avgFillPrice=1.0),
                log=[types.SimpleNamespace(time=pd.Timestamp('2020-01-01'))],
            )

        def sleep(self, _):
            pass

        def cancelOrder(self, order):
            pass

    def Stock(symbol, exchange, currency):
        return object()

    def MarketOrder(action, qty):
        return types.SimpleNamespace(orderType='MKT')

    ib_module = types.ModuleType('ib_insync')
    ib_module.IB = DummyIB
    ib_module.Stock = Stock
    ib_module.MarketOrder = MarketOrder
    ib_module.LimitOrder = lambda *args, **kwargs: types.SimpleNamespace(orderType='LMT')
    sys.modules['ib_insync'] = ib_module

    from importlib import reload
    from pwb_toolbox.execution import ib_connector

    reload(ib_connector)
    connector = ib_connector.IBConnector()

    trades = connector.execute_orders({'AAPL': 1}, time_in_seconds=0)

    assert connector.ib.connect_calls == 2
    assert connector.ib.place_order_calls == 2
    assert len(trades) == 1
