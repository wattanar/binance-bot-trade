from decimal import Decimal

import pytest

from src.config import (
    GridConfig,
    GridType,
    RiskConfig,
    load_config,
    ConfigError,
)


class TestGridConfig:
    def test_arithmetic_grid_is_valid(self):
        cfg = GridConfig(
            symbol="BTC/USDT:USDT",
            grid_type=GridType.ARITHMETIC,
            upper_price=Decimal("110000.0"),
            lower_price=Decimal("90000.0"),
            grid_count=10,
            order_size=Decimal("0.001"),
            leverage=2,
        )
        cfg.validate()

    def test_geometric_grid_is_valid(self):
        cfg = GridConfig(
            symbol="ETH/USDT:USDT",
            grid_type=GridType.GEOMETRIC,
            upper_price=Decimal("4000.0"),
            lower_price=Decimal("2000.0"),
            grid_count=5,
            order_size=Decimal("0.01"),
            leverage=3,
        )
        cfg.validate()

    def test_rejects_upper_below_lower(self):
        cfg = GridConfig(
            symbol="BTC/USDT:USDT",
            grid_type=GridType.ARITHMETIC,
            upper_price=Decimal("90000.0"),
            lower_price=Decimal("110000.0"),
            grid_count=10,
            order_size=Decimal("0.001"),
            leverage=1,
        )
        with pytest.raises(ValueError, match="upper_price"):
            cfg.validate()

    def test_rejects_equal_upper_lower(self):
        cfg = GridConfig(
            symbol="BTC/USDT:USDT",
            grid_type=GridType.ARITHMETIC,
            upper_price=Decimal("100000.0"),
            lower_price=Decimal("100000.0"),
            grid_count=10,
            order_size=Decimal("0.001"),
            leverage=1,
        )
        with pytest.raises(ValueError, match="upper_price"):
            cfg.validate()

    def test_rejects_grid_count_less_than_2(self):
        cfg = GridConfig(
            symbol="BTC/USDT:USDT",
            grid_type=GridType.ARITHMETIC,
            upper_price=Decimal("110000.0"),
            lower_price=Decimal("90000.0"),
            grid_count=1,
            order_size=Decimal("0.001"),
            leverage=1,
        )
        with pytest.raises(ValueError, match="grid_count"):
            cfg.validate()

    def test_rejects_negative_order_size(self):
        cfg = GridConfig(
            symbol="BTC/USDT:USDT",
            grid_type=GridType.ARITHMETIC,
            upper_price=Decimal("110000.0"),
            lower_price=Decimal("90000.0"),
            grid_count=10,
            order_size=Decimal("-0.001"),
            leverage=1,
        )
        with pytest.raises(ValueError, match="order_size"):
            cfg.validate()

    def test_rejects_zero_order_size(self):
        cfg = GridConfig(
            symbol="BTC/USDT:USDT",
            grid_type=GridType.ARITHMETIC,
            upper_price=Decimal("110000.0"),
            lower_price=Decimal("90000.0"),
            grid_count=10,
            order_size=Decimal("0"),
            leverage=1,
        )
        with pytest.raises(ValueError, match="order_size"):
            cfg.validate()

    def test_rejects_zero_leverage(self):
        cfg = GridConfig(
            symbol="BTC/USDT:USDT",
            grid_type=GridType.ARITHMETIC,
            upper_price=Decimal("110000.0"),
            lower_price=Decimal("90000.0"),
            grid_count=10,
            order_size=Decimal("0.001"),
            leverage=0,
        )
        with pytest.raises(ValueError, match="leverage"):
            cfg.validate()

    def test_geometric_rejects_zero_lower_price(self):
        cfg = GridConfig(
            symbol="BTC/USDT:USDT",
            grid_type=GridType.GEOMETRIC,
            upper_price=Decimal("100000.0"),
            lower_price=Decimal("0"),
            grid_count=5,
            order_size=Decimal("0.001"),
            leverage=1,
        )
        with pytest.raises(ValueError, match="lower_price"):
            cfg.validate()


class TestRiskConfig:
    def test_valid_risk_config(self):
        cfg = RiskConfig(max_position_btc=Decimal("0.01"), max_grid_count=20, stop_loss_pct=Decimal("-5.0"))
        cfg.validate()

    def test_rejects_negative_max_position(self):
        cfg = RiskConfig(max_position_btc=Decimal("-0.1"), max_grid_count=20, stop_loss_pct=Decimal("-5.0"))
        with pytest.raises(ValueError, match="max_position"):
            cfg.validate()

    def test_rejects_positive_stop_loss(self):
        cfg = RiskConfig(max_position_btc=Decimal("0.01"), max_grid_count=20, stop_loss_pct=Decimal("5.0"))
        with pytest.raises(ValueError, match="stop_loss"):
            cfg.validate()


class TestBotConfig:
    def test_load_from_valid_yaml(self, tmp_path):
        yaml_content = """
exchange: binance
symbol: BTC/USDT:USDT
grid:
  type: arithmetic
  upper_price: 110000.0
  lower_price: 90000.0
  grid_count: 10
  order_size: 0.001
  leverage: 2
risk:
  max_position_btc: 0.01
  max_grid_count: 20
  stop_loss_pct: -5.0
backtest:
  trading_fee_pct: 0.04
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml_content)
        cfg = load_config(str(config_file))
        assert cfg.symbol == "BTC/USDT:USDT"
        assert cfg.grid.grid_type == GridType.ARITHMETIC
        assert cfg.grid.grid_count == 10
        assert cfg.risk.max_grid_count == 20

    def test_load_geometric_grid(self, tmp_path):
        yaml_content = """
exchange: binance
symbol: ETH/USDT:USDT
grid:
  type: geometric
  upper_price: 4000.0
  lower_price: 2000.0
  grid_count: 5
  order_size: 0.01
  leverage: 3
risk:
  max_position_btc: 0.5
  max_grid_count: 10
  stop_loss_pct: -10.0
backtest:
  trading_fee_pct: 0.04
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml_content)
        cfg = load_config(str(config_file))
        assert cfg.grid.grid_type == GridType.GEOMETRIC
        assert cfg.grid.upper_price == Decimal("4000.0")
        assert cfg.symbol == "ETH/USDT:USDT"

    def test_rejects_missing_field(self, tmp_path):
        yaml_content = """
exchange: binance
grid:
  type: arithmetic
  upper_price: 110000.0
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml_content)
        with pytest.raises(ConfigError):
            load_config(str(config_file))

    def test_rejects_invalid_grid_type(self, tmp_path):
        yaml_content = """
exchange: binance
symbol: BTC/USDT:USDT
grid:
  type: fibonacci
  upper_price: 110000.0
  lower_price: 90000.0
  grid_count: 10
  order_size: 0.001
  leverage: 2
risk:
  max_position_btc: 0.01
  max_grid_count: 20
  stop_loss_pct: -5.0
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml_content)
        with pytest.raises(ConfigError):
            load_config(str(config_file))
