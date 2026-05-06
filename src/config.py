from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import Enum

import yaml


class ConfigError(Exception):
    pass


class GridType(str, Enum):
    ARITHMETIC = "arithmetic"
    GEOMETRIC = "geometric"


@dataclass
class GridConfig:
    symbol: str
    grid_type: GridType
    upper_price: Decimal
    lower_price: Decimal
    grid_count: int
    order_size: Decimal
    leverage: int = 1

    def validate(self) -> None:
        if self.upper_price <= self.lower_price:
            raise ValueError("upper_price must be greater than lower_price")
        if self.grid_count < 2:
            raise ValueError("grid_count must be at least 2")
        if self.order_size <= Decimal("0"):
            raise ValueError("order_size must be positive")
        if self.leverage < 1:
            raise ValueError("leverage must be at least 1")
        if self.grid_type == GridType.GEOMETRIC and self.lower_price <= Decimal("0"):
            raise ValueError("lower_price must be positive for geometric grid")


@dataclass
class RiskConfig:
    max_position_btc: Decimal
    max_grid_count: int
    stop_loss_pct: Decimal

    def validate(self) -> None:
        if self.max_position_btc < Decimal("0"):
            raise ValueError("max_position_btc must be non-negative")
        if self.max_grid_count < 1:
            raise ValueError("max_grid_count must be at least 1")
        if self.stop_loss_pct > Decimal("0"):
            raise ValueError("stop_loss_pct must be negative or zero")


@dataclass
class BacktestConfig:
    trading_fee_pct: Decimal = Decimal("0.04")


@dataclass
class BotConfig:
    symbol: str
    grid: GridConfig
    risk: RiskConfig
    backtest: BacktestConfig = field(default_factory=BacktestConfig)

    def validate(self) -> None:
        self.grid.validate()
        self.risk.validate()

    @property
    def exchange(self) -> str:
        return "binance"


def _to_decimal(value: str | int | float | Decimal) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as e:
        raise ConfigError(f"Invalid decimal value: {value}") from e


def load_config(path: str) -> BotConfig:
    with open(path) as f:
        raw = yaml.safe_load(f)

    if raw is None:
        raise ConfigError("Config file is empty")

    try:
        symbol = raw["symbol"]

        grid_raw = raw.get("grid", {})
        grid_type_str = grid_raw.get("type", "arithmetic")
        try:
            grid_type = GridType(grid_type_str)
        except ValueError:
            raise ConfigError(f"Invalid grid type: {grid_type_str}. Must be 'arithmetic' or 'geometric'")

        grid = GridConfig(
            symbol=symbol,
            grid_type=grid_type,
            upper_price=_to_decimal(grid_raw["upper_price"]),
            lower_price=_to_decimal(grid_raw["lower_price"]),
            grid_count=int(grid_raw["grid_count"]),
            order_size=_to_decimal(grid_raw["order_size"]),
            leverage=int(grid_raw.get("leverage", 1)),
        )

        risk_raw = raw.get("risk", {})
        risk = RiskConfig(
            max_position_btc=_to_decimal(risk_raw.get("max_position_btc", "0.01")),
            max_grid_count=int(risk_raw.get("max_grid_count", 20)),
            stop_loss_pct=_to_decimal(risk_raw.get("stop_loss_pct", "-5.0")),
        )

        backtest_raw = raw.get("backtest", {})
        backtest = BacktestConfig(
            trading_fee_pct=_to_decimal(backtest_raw.get("trading_fee_pct", "0.04")),
        )

        bot_config = BotConfig(
            symbol=symbol,
            grid=grid,
            risk=risk,
            backtest=backtest,
        )
        bot_config.validate()
        return bot_config

    except KeyError as e:
        raise ConfigError(f"Missing required config field: {e.args[0]}") from e
    except (TypeError, ValueError) as e:
        raise ConfigError(f"Invalid configuration: {e}") from e
