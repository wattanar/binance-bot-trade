from decimal import Decimal

import pytest

from src.grid_strategy import (
    calculate_grid_levels,
    split_levels_by_price,
    next_target_level,
    generate_initial_orders,
    rebalance_after_fill,
    identify_stale_orders,
    OrderIntent,
    GridConfig,
    GridType,
)


class TestCalculateGridLevels:
    def test_arithmetic_grid_5_levels(self):
        levels = calculate_grid_levels(
            GridConfig(
                symbol="BTC/USDT:USDT",
                grid_type=GridType.ARITHMETIC,
                upper_price=Decimal("100000"),
                lower_price=Decimal("80000"),
                grid_count=5,
                order_size=Decimal("0.001"),
            )
        )
        assert len(levels) == 5
        assert levels[0] == Decimal("80000")
        assert levels[-1] == Decimal("100000")
        assert levels[1] == Decimal("85000")
        assert levels[2] == Decimal("90000")
        assert levels[3] == Decimal("95000")

    def test_arithmetic_grid_2_levels(self):
        levels = calculate_grid_levels(
            GridConfig(
                symbol="BTC/USDT:USDT",
                grid_type=GridType.ARITHMETIC,
                upper_price=Decimal("110000"),
                lower_price=Decimal("90000"),
                grid_count=2,
                order_size=Decimal("0.001"),
            )
        )
        assert len(levels) == 2
        assert levels[0] == Decimal("90000")
        assert levels[1] == Decimal("110000")

    def test_arithmetic_grid_8_levels(self):
        levels = calculate_grid_levels(
            GridConfig(
                symbol="BTC/USDT:USDT",
                grid_type=GridType.ARITHMETIC,
                upper_price=Decimal("100"),
                lower_price=Decimal("30"),
                grid_count=8,
                order_size=Decimal("1"),
            )
        )
        assert len(levels) == 8
        step = levels[1] - levels[0]
        assert step == Decimal("10")
        for i in range(7):
            assert levels[i + 1] - levels[i] == step

    def test_geometric_grid_3_levels(self):
        levels = calculate_grid_levels(
            GridConfig(
                symbol="BTC/USDT:USDT",
                grid_type=GridType.GEOMETRIC,
                upper_price=Decimal("122.5"),
                lower_price=Decimal("100"),
                grid_count=3,
                order_size=Decimal("0.001"),
            )
        )
        assert len(levels) == 3
        assert levels[0] == Decimal("100")
        assert levels[-1] == Decimal("122.5")
        ratio = levels[1] / levels[0]
        assert ratio == pytest.approx(Decimal("1.10679"), rel=Decimal("1e-4"))
        assert levels[1] * ratio == pytest.approx(levels[2], rel=Decimal("1e-4"))

    def test_geometric_grid_constant_ratio(self):
        levels = calculate_grid_levels(
            GridConfig(
                symbol="BTC/USDT:USDT",
                grid_type=GridType.GEOMETRIC,
                upper_price=Decimal("200000"),
                lower_price=Decimal("50000"),
                grid_count=5,
                order_size=Decimal("0.001"),
            )
        )
        assert len(levels) == 5
        ratio = levels[1] / levels[0]
        for i in range(4):
            assert levels[i + 1] / levels[i] == pytest.approx(ratio, rel=Decimal("1e-8"))

    def test_arithmetic_grid_is_sorted(self):
        levels = calculate_grid_levels(
            GridConfig(
                symbol="BTC/USDT:USDT",
                grid_type=GridType.ARITHMETIC,
                upper_price=Decimal("100000"),
                lower_price=Decimal("50000"),
                grid_count=10,
                order_size=Decimal("0.001"),
            )
        )
        assert levels == sorted(levels)


class TestSplitLevelsByPrice:
    def setup_method(self):
        self.levels = [
            Decimal("90"),
            Decimal("92"),
            Decimal("94"),
            Decimal("96"),
            Decimal("98"),
            Decimal("100"),
            Decimal("102"),
            Decimal("104"),
            Decimal("106"),
            Decimal("108"),
        ]

    def test_split_middle_price(self):
        buys, sells = split_levels_by_price(self.levels, Decimal("100"))
        assert buys == self.levels[:5]
        assert sells == self.levels[5:]

    def test_split_price_below_all(self):
        buys, sells = split_levels_by_price(self.levels, Decimal("85"))
        assert buys == []
        assert sells == self.levels

    def test_split_price_above_all(self):
        buys, sells = split_levels_by_price(self.levels, Decimal("115"))
        assert buys == self.levels
        assert sells == []

    def test_split_price_at_boundary(self):
        buys, sells = split_levels_by_price(self.levels, Decimal("90"))
        assert buys == []
        assert sells == self.levels


class TestNextTargetLevel:
    def test_buy_fill_next_sell(self):
        step = Decimal("100")
        result = next_target_level(
            filled_level=Decimal("50000"),
            side="buy",
            step=step,
        )
        assert result == Decimal("50100")

    def test_sell_fill_next_buy(self):
        step = Decimal("100")
        result = next_target_level(
            filled_level=Decimal("50000"),
            side="sell",
            step=step,
        )
        assert result == Decimal("49900")

    def test_fractional_step(self):
        step = Decimal("2.5")
        buy_result = next_target_level(
            filled_level=Decimal("100"),
            side="buy",
            step=step,
        )
        sell_result = next_target_level(
            filled_level=Decimal("100"),
            side="sell",
            step=step,
        )
        assert buy_result == Decimal("102.5")
        assert sell_result == Decimal("97.5")


class TestGenerateInitialOrders:
    def test_places_buys_below_sells_above(self):
        levels = [Decimal("90"), Decimal("92"), Decimal("94"), Decimal("96"), Decimal("98")]
        current_price = Decimal("94")
        orders = generate_initial_orders(levels, current_price, Decimal("0.001"))

        assert len(orders) == 5
        buys = [o for o in orders if o.side == "buy"]
        sells = [o for o in orders if o.side == "sell"]
        assert len(buys) == 2
        assert len(sells) == 3
        assert all(o.price < current_price for o in buys)
        assert all(o.price >= current_price for o in sells)
        assert all(o.amount == Decimal("0.001") for o in orders)

    def test_price_above_all_levels(self):
        levels = [Decimal("90"), Decimal("95"), Decimal("100")]
        current_price = Decimal("105")
        orders = generate_initial_orders(levels, current_price, Decimal("0.001"))

        buys = [o for o in orders if o.side == "buy"]
        sells = [o for o in orders if o.side == "sell"]
        assert len(buys) == 3
        assert len(sells) == 0

    def test_price_below_all_levels(self):
        levels = [Decimal("90"), Decimal("95"), Decimal("100")]
        current_price = Decimal("85")
        orders = generate_initial_orders(levels, current_price, Decimal("0.001"))

        buys = [o for o in orders if o.side == "buy"]
        sells = [o for o in orders if o.side == "sell"]
        assert len(buys) == 0
        assert len(sells) == 3

    def test_order_intent_structure(self):
        levels = [Decimal("100")]
        current_price = Decimal("105")

        orders = generate_initial_orders(levels, current_price, Decimal("0.01"))
        assert len(orders) == 1
        order = orders[0]
        assert order.symbol is not None
        assert order.side == "buy"
        assert order.price == Decimal("100")
        assert order.amount == Decimal("0.01")


class TestRebalanceAfterFill:
    def test_buy_fill_places_sell_above(self):
        all_levels = [Decimal("90"), Decimal("100"), Decimal("110")]
        step = Decimal("10")

        filled = OrderIntent(symbol="BTC/USDT:USDT", side="buy", price=Decimal("90"), amount=Decimal("0.001"))
        result = rebalance_after_fill(filled, all_levels, step, Decimal("0.001"))

        assert result.side == "sell"
        assert result.price == Decimal("100")
        assert result.amount == Decimal("0.001")

    def test_sell_fill_places_buy_below(self):
        all_levels = [Decimal("90"), Decimal("100"), Decimal("110")]
        step = Decimal("10")

        filled = OrderIntent(symbol="BTC/USDT:USDT", side="sell", price=Decimal("110"), amount=Decimal("0.001"))
        result = rebalance_after_fill(filled, all_levels, step, Decimal("0.001"))

        assert result.side == "buy"
        assert result.price == Decimal("100")
        assert result.amount == Decimal("0.001")

    def test_buy_at_lowest_level_no_below(self):
        all_levels = [Decimal("90"), Decimal("100")]
        step = Decimal("10")

        filled = OrderIntent(symbol="BTC/USDT:USDT", side="sell", price=Decimal("90"), amount=Decimal("0.001"))
        result = rebalance_after_fill(filled, all_levels, step, Decimal("0.001"))

        assert result is None


class TestIdentifyStaleOrders:
    def test_orders_at_levels_not_stale(self):
        open_orders = [
            {"id": "1", "price": 100.0, "side": "buy"},
            {"id": "2", "price": 110.0, "side": "sell"},
        ]
        current_levels = [Decimal("100"), Decimal("110"), Decimal("120")]

        stale = identify_stale_orders(open_orders, current_levels)
        assert stale == []

    def test_order_outside_levels_is_stale(self):
        open_orders = [
            {"id": "1", "price": 100.0, "side": "buy"},
            {"id": "2", "price": 95.0, "side": "buy"},
        ]
        current_levels = [Decimal("100"), Decimal("110")]

        stale = identify_stale_orders(open_orders, current_levels)
        assert "2" in stale
        assert "1" not in stale

    def test_all_orders_stale(self):
        open_orders = [
            {"id": "1", "price": 80.0, "side": "buy"},
            {"id": "2", "price": 130.0, "side": "sell"},
        ]
        current_levels = [Decimal("100"), Decimal("110")]

        stale = identify_stale_orders(open_orders, current_levels)
        assert set(stale) == {"1", "2"}

    def test_empty_orders(self):
        stale = identify_stale_orders([], [Decimal("100"), Decimal("110")])
        assert stale == []

    def test_empty_levels(self):
        open_orders = [{"id": "1", "price": 100.0, "side": "buy"}]
        stale = identify_stale_orders(open_orders, [])
        assert stale == ["1"]
