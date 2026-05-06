from decimal import Decimal


from src.backtester import SimulatedExchange, compute_metrics
from src.grid_strategy import OrderIntent


class TestSimulatedExchange:
    def test_initial_state(self):
        ex = SimulatedExchange()
        assert ex.cash == Decimal("0")
        assert ex.position == Decimal("0")
        assert len(ex.orders) == 0

    def test_place_order(self):
        ex = SimulatedExchange()
        order = OrderIntent(symbol="BTC", side="buy", price=Decimal("50000"), amount=Decimal("0.001"))
        oid = ex.place_order(order)
        assert oid == "1"
        assert ex.orders["1"].side == "buy"

    def test_cancel_order(self):
        ex = SimulatedExchange()
        order = OrderIntent(symbol="BTC", side="buy", price=Decimal("50000"), amount=Decimal("0.001"))
        oid = ex.place_order(order)
        ex.cancel_order(oid)
        assert len(ex.orders) == 0

    def test_buy_fill_on_candle_low(self):
        ex = SimulatedExchange(fee_rate=Decimal("0.0004"))
        order = OrderIntent(symbol="BTC", side="buy", price=Decimal("50000"), amount=Decimal("0.001"))
        ex.place_order(order)

        fills = ex.process_candle(high=Decimal("51000"), low=Decimal("49900"), close=Decimal("50500"))
        assert len(fills) == 1
        assert fills[0].price == Decimal("50000")
        assert ex.position == Decimal("0.001")
        assert len(ex.orders) == 0

    def test_sell_fill_on_candle_high(self):
        ex = SimulatedExchange(fee_rate=Decimal("0.0004"))
        ex.position = Decimal("0.001")
        order = OrderIntent(symbol="BTC", side="sell", price=Decimal("51000"), amount=Decimal("0.001"))
        ex.place_order(order)

        fills = ex.process_candle(high=Decimal("51500"), low=Decimal("50500"), close=Decimal("50800"))
        assert len(fills) == 1
        assert fills[0].price == Decimal("51000")
        assert ex.position == Decimal("0")

    def test_no_fill_if_price_not_crossed(self):
        ex = SimulatedExchange()
        order = OrderIntent(symbol="BTC", side="buy", price=Decimal("50000"), amount=Decimal("0.001"))
        ex.place_order(order)

        fills = ex.process_candle(high=Decimal("50500"), low=Decimal("50100"), close=Decimal("50300"))
        assert len(fills) == 0
        assert len(ex.orders) == 1

    def test_multiple_fills_in_one_candle(self):
        ex = SimulatedExchange(fee_rate=Decimal("0.0004"))
        ex.place_order(OrderIntent(symbol="BTC", side="buy", price=Decimal("50000"), amount=Decimal("0.001")))
        ex.place_order(OrderIntent(symbol="BTC", side="sell", price=Decimal("52000"), amount=Decimal("0.001")))
        ex.position = Decimal("0.001")

        fills = ex.process_candle(high=Decimal("53000"), low=Decimal("49000"), close=Decimal("51000"))
        assert len(fills) == 2

    def test_equity_calculation(self):
        ex = SimulatedExchange()
        ex.cash = Decimal("10000")
        ex.position = Decimal("0.001")
        equity = ex.equity(Decimal("50000"))
        assert equity == Decimal("10000") + Decimal("0.001") * Decimal("50000")


class TestComputeMetrics:
    def test_flat_curve_metrics(self):
        eq = [1000.0, 1000.0, 1000.0]
        result = compute_metrics(eq, 1000.0, [])
        assert float(result.total_pnl) == 0.0
        assert float(result.max_drawdown_pct) == 0.0
        assert result.trade_count == 0
        assert result.win_count == 0

    def test_profitable_curve(self):
        eq = [1000.0, 1001.0, 1002.0, 1003.0, 1004.0, 1005.0]
        result = compute_metrics(eq, 1000.0, [1.0, 1.0, 1.0, 1.0, 1.0])
        assert float(result.total_pnl) == 5.0
        assert result.trade_count == 5
        assert result.win_count == 5
        assert result.losing_count == 0

    def test_mixed_trades(self):
        eq = [1000.0, 1010.0, 1005.0, 1020.0]
        result = compute_metrics(eq, 1000.0, [10.0, -5.0, 15.0])
        assert result.win_count == 2
        assert result.losing_count == 1
        assert float(result.total_pnl) == 20.0

    def test_drawdown_calculation(self):
        eq = [1000.0, 900.0, 950.0, 800.0, 850.0, 1000.0]
        result = compute_metrics(eq, 1000.0, [])
        assert result.max_drawdown_pct > 0
