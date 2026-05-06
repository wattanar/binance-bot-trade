from decimal import Decimal


from src.config import RiskConfig
from src.grid_strategy import OrderIntent
from src.risk_manager import (
    validate_order,
    check_grid_limit,
    should_stop_loss,
    calculate_position_size,
    round_price,
    round_quantity,
)


class TestValidateOrder:
    def setup_method(self):
        self.risk = RiskConfig(
            max_position_btc=Decimal("0.01"),
            max_grid_count=20,
            stop_loss_pct=Decimal("-5.0"),
        )

    def test_order_within_limit_allowed(self):
        order = OrderIntent(symbol="BTC", side="buy", price=Decimal("100000"), amount=Decimal("0.001"))
        current_position = Decimal("0.002")
        assert validate_order(order, current_position, self.risk) is True

    def test_order_exceeds_max_position_rejected(self):
        order = OrderIntent(symbol="BTC", side="buy", price=Decimal("100000"), amount=Decimal("0.01"))
        current_position = Decimal("0.009")
        assert validate_order(order, current_position, self.risk) is False

    def test_sell_order_always_allowed_when_within_range(self):
        order = OrderIntent(symbol="BTC", side="sell", price=Decimal("100000"), amount=Decimal("0.01"))
        current_position = Decimal("0.005")
        assert validate_order(order, current_position, self.risk) is True

    def test_exact_position_limit_allowed(self):
        order = OrderIntent(symbol="BTC", side="buy", price=Decimal("100000"), amount=Decimal("0.005"))
        current_position = Decimal("0.005")
        assert validate_order(order, current_position, self.risk) is True


class TestCheckGridLimit:
    def test_under_limit_ok(self):
        assert check_grid_limit(10, RiskConfig(
            max_position_btc=Decimal("0.01"),
            max_grid_count=20,
            stop_loss_pct=Decimal("-5.0"),
        )) is True

    def test_exactly_at_limit_ok(self):
        assert check_grid_limit(20, RiskConfig(
            max_position_btc=Decimal("0.01"),
            max_grid_count=20,
            stop_loss_pct=Decimal("-5.0"),
        )) is True

    def test_over_limit(self):
        assert check_grid_limit(21, RiskConfig(
            max_position_btc=Decimal("0.01"),
            max_grid_count=20,
            stop_loss_pct=Decimal("-5.0"),
        )) is False


class TestShouldStopLoss:
    def test_pnl_within_range(self):
        risk = RiskConfig(
            max_position_btc=Decimal("0.01"),
            max_grid_count=20,
            stop_loss_pct=Decimal("-5.0"),
        )
        assert should_stop_loss(Decimal("-2.0"), risk) is False

    def test_pnl_at_threshold(self):
        risk = RiskConfig(
            max_position_btc=Decimal("0.01"),
            max_grid_count=20,
            stop_loss_pct=Decimal("-5.0"),
        )
        assert should_stop_loss(Decimal("-5.0"), risk) is True

    def test_pnl_below_threshold(self):
        risk = RiskConfig(
            max_position_btc=Decimal("0.01"),
            max_grid_count=20,
            stop_loss_pct=Decimal("-5.0"),
        )
        assert should_stop_loss(Decimal("-10.0"), risk) is True

    def test_positive_pnl_no_stop(self):
        risk = RiskConfig(
            max_position_btc=Decimal("0.01"),
            max_grid_count=20,
            stop_loss_pct=Decimal("-5.0"),
        )
        assert should_stop_loss(Decimal("3.0"), risk) is False


class TestCalculatePositionSize:
    def test_sum_positions(self):
        positions = [
            {"contracts": 0.001, "side": "long"},
            {"contracts": 0.002, "side": "long"},
        ]
        size = calculate_position_size(positions)
        assert size == Decimal("0.003")

    def test_empty_positions(self):
        size = calculate_position_size([])
        assert size == Decimal("0")

    def test_short_positions(self):
        positions = [
            {"contracts": 0.001, "side": "short"},
            {"contracts": 0.003, "side": "short"},
        ]
        size = calculate_position_size(positions)
        assert size == Decimal("0.004")

    def test_mixed_long_short(self):
        positions = [
            {"contracts": 0.005, "side": "long"},
            {"contracts": 0.003, "side": "short"},
        ]
        size = calculate_position_size(positions)
        assert size == Decimal("0.008")


class TestRoundPrice:
    def test_round_to_tick(self):
        assert round_price(Decimal("50000.123"), Decimal("0.01")) == Decimal("50000.12")

    def test_round_up_at_half(self):
        assert round_price(Decimal("100.005"), Decimal("0.01")) == Decimal("100.01")

    def test_already_aligned(self):
        assert round_price(Decimal("100.00"), Decimal("0.01")) == Decimal("100.00")

    def test_small_tick_size(self):
        assert round_price(Decimal("50000.12345678"), Decimal("0.1")) == Decimal("50000.1")


class TestRoundQuantity:
    def test_round_down_for_safety(self):
        assert round_quantity(Decimal("0.0015"), Decimal("0.001")) == Decimal("0.001")

    def test_round_down_same_as_round_up(self):
        assert round_quantity(Decimal("0.0015"), Decimal("0.001")) == Decimal("0.001")

    def test_already_aligned(self):
        assert round_quantity(Decimal("0.001"), Decimal("0.001")) == Decimal("0.001")

    def test_round_down_on_overage(self):
        assert round_quantity(Decimal("0.0019"), Decimal("0.001")) == Decimal("0.001")
