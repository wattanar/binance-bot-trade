from dataclasses import dataclass, field
from decimal import Decimal

import numpy as np
import pandas as pd

from src.config import BotConfig
from src.grid_strategy import (
    OrderIntent,
    calculate_grid_levels,
    generate_initial_orders,
    rebalance_after_fill,
)


@dataclass
class BacktestResult:
    total_pnl: Decimal = Decimal("0")
    total_return_pct: Decimal = Decimal("0")
    sharpe_ratio: Decimal = Decimal("0")
    max_drawdown_pct: Decimal = Decimal("0")
    trade_count: int = 0
    win_count: int = 0
    losing_count: int = 0
    profit_factor: Decimal = Decimal("0")
    equity_curve: list[float] = field(default_factory=list)

    def summary_table(self) -> str:
        lines = [
            "══════════════════════════════════",
            "         BACKTEST RESULTS         ",
            "══════════════════════════════════",
            f"  Total PnL:          ${float(self.total_pnl):>12,.2f}",
            f"  Total Return:       {float(self.total_return_pct):>11.2f}%",
            f"  Sharpe Ratio:       {float(self.sharpe_ratio):>13.2f}",
            f"  Max Drawdown:       {float(self.max_drawdown_pct):>11.2f}%",
            f"  Trade Count:        {self.trade_count:>12d}",
            f"  Win Rate:           {self._win_rate():>11.1f}%",
            f"  Profit Factor:      {float(self.profit_factor):>13.2f}",
            "══════════════════════════════════",
        ]
        return "\n".join(lines)

    def _win_rate(self) -> float:
        if self.trade_count == 0:
            return 0.0
        return (self.win_count / self.trade_count) * 100


class SimulatedExchange:
    def __init__(self, fee_rate: Decimal = Decimal("0.0004")):
        self.fee_rate = fee_rate
        self.orders: dict[str, OrderIntent] = {}
        self.position: Decimal = Decimal("0")
        self.cash: Decimal = Decimal("0")
        self.avg_entry_price: Decimal = Decimal("0")
        self.order_counter: int = 0

    def place_order(self, order: OrderIntent) -> str:
        self.order_counter += 1
        oid = str(self.order_counter)
        order.order_id = oid
        self.orders[oid] = order
        return oid

    def cancel_order(self, order_id: str) -> None:
        self.orders.pop(order_id, None)

    def get_open_orders(self) -> list[OrderIntent]:
        return list(self.orders.values())

    def equity(self, current_price: Decimal) -> Decimal:
        position_value = self.position * current_price
        return self.cash + position_value

    def process_candle(self, high: Decimal, low: Decimal, close: Decimal) -> list[OrderIntent]:
        filled = []
        to_remove = []

        for oid, order in self.orders.items():
            filled_order = None
            if order.side == "buy" and low <= order.price:
                fill_price = order.price
                filled_order = order
            elif order.side == "sell" and high >= order.price:
                fill_price = order.price
                filled_order = order

            if filled_order:
                fee = filled_order.amount * fill_price * self.fee_rate
                if filled_order.side == "buy":
                    self.cash -= filled_order.amount * fill_price + fee
                    self.position += filled_order.amount
                else:
                    self.cash += filled_order.amount * fill_price - fee
                    self.position -= filled_order.amount

                filled.append(filled_order)
                to_remove.append(oid)

        for oid in to_remove:
            self.orders.pop(oid)

        return filled


def compute_metrics(
    equity_curve: list[float],
    initial_equity: float,
    trade_pnls: list[float],
) -> BacktestResult:
    if not equity_curve or len(equity_curve) < 2:
        return BacktestResult()

    returns = np.diff(equity_curve) / equity_curve[:-1]

    total_pnl = equity_curve[-1] - initial_equity
    total_return_pct = (total_pnl / initial_equity) * 100

    if len(returns) > 0 and np.std(returns) > 0:
        sharpe = np.sqrt(365 * 24 * 60) * np.mean(returns) / np.std(returns)
    else:
        sharpe = 0

    peak = np.maximum.accumulate(equity_curve)
    drawdowns = (peak - equity_curve) / peak * 100
    max_drawdown = max(drawdowns) if len(drawdowns) > 0 else 0

    win_count = sum(1 for p in trade_pnls if p > 0)
    losing_count = sum(1 for p in trade_pnls if p < 0)

    total_profit = sum(p for p in trade_pnls if p > 0)
    total_loss = abs(sum(p for p in trade_pnls if p < 0))

    if total_loss > 0:
        profit_factor = total_profit / total_loss
    else:
        profit_factor = float("inf") if total_profit > 0 else 0

    return BacktestResult(
        total_pnl=Decimal(str(round(total_pnl, 2))),
        total_return_pct=Decimal(str(round(total_return_pct, 2))),
        sharpe_ratio=Decimal(str(round(sharpe, 4))),
        max_drawdown_pct=Decimal(str(round(max_drawdown, 2))),
        trade_count=len(trade_pnls),
        win_count=win_count,
        losing_count=losing_count,
        profit_factor=Decimal(str(round(profit_factor, 2))),
        equity_curve=equity_curve,
    )


async def run_backtest(config: BotConfig, ohlcv: pd.DataFrame) -> BacktestResult:
    levels = calculate_grid_levels(config.grid)
    step = (config.grid.upper_price - config.grid.lower_price) / (config.grid_count - 1)

    exchange = SimulatedExchange(fee_rate=config.backtest.trading_fee_pct / Decimal("100"))
    initial_capital = config.grid.order_size * config.grid.grid_count * config.grid.upper_price
    exchange.cash = initial_capital

    trade_pnls: list[float] = []
    equity_curve: list[float] = [float(exchange.equity(Decimal(str(ohlcv.iloc[0]["close"]))))]

    for i, row in ohlcv.iterrows():
        current_price = Decimal(str(row["close"]))
        high = Decimal(str(row["high"]))
        low = Decimal(str(row["low"]))

        if i == 0:
            initial_orders = generate_initial_orders(levels, current_price, config.grid.order_size, config.symbol)
            for order in initial_orders:
                exchange.place_order(order)

        fills = exchange.process_candle(high, low, current_price)

        for filled in fills:
            entry_px = float(filled.price)
            exit_px = float(next_target_level_px(filled, step))
            grid_profit = (exit_px - entry_px) * float(config.grid.order_size)
            trade_pnls.append(grid_profit)

            rebalance_order = rebalance_after_fill(filled, levels, step, config.grid.order_size)
            if rebalance_order is not None:
                exchange.place_order(rebalance_order)

        equity_curve.append(float(exchange.equity(current_price)))

    return compute_metrics(equity_curve, float(initial_capital), trade_pnls)


def next_target_level_px(order: OrderIntent, step: Decimal) -> Decimal:
    if order.side == "buy":
        return order.price + step
    return order.price - step
