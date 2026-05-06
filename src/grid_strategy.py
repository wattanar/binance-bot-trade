from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from src.config import GridConfig, GridType


@dataclass
class OrderIntent:
    symbol: str
    side: str
    price: Decimal
    amount: Decimal
    order_id: Optional[str] = None


def calculate_grid_levels(config: GridConfig) -> list[Decimal]:
    if config.grid_type == GridType.ARITHMETIC:
        step = (config.upper_price - config.lower_price) / (config.grid_count - 1)
        return [config.lower_price + step * i for i in range(config.grid_count)]

    ratio = Decimal(
        (float(config.upper_price) / float(config.lower_price))
        ** (1.0 / (config.grid_count - 1))
    )
    levels = [config.lower_price]
    for _ in range(config.grid_count - 2):
        levels.append(levels[-1] * ratio)
    levels.append(config.upper_price)
    return levels


def split_levels_by_price(
    levels: list[Decimal],
    current_price: Decimal,
) -> tuple[list[Decimal], list[Decimal]]:
    buys = [level for level in levels if level < current_price]
    sells = [level for level in levels if level >= current_price]
    return buys, sells


def next_target_level(
    filled_level: Decimal,
    side: str,
    step: Decimal,
) -> Decimal:
    if side == "buy":
        return filled_level + step
    return filled_level - step


def generate_initial_orders(
    levels: list[Decimal],
    current_price: Decimal,
    order_size: Decimal,
    symbol: str = "",
) -> list[OrderIntent]:
    orders = []
    for level in levels:
        side = "buy" if level < current_price else "sell"
        orders.append(OrderIntent(symbol=symbol, side=side, price=level, amount=order_size))
    return orders


def rebalance_after_fill(
    filled: OrderIntent,
    all_levels: list[Decimal],
    step: Decimal,
    order_size: Decimal,
) -> Optional[OrderIntent]:
    target = next_target_level(filled.price, filled.side, step)
    if target not in all_levels:
        return None
    opposite_side = "sell" if filled.side == "buy" else "buy"
    return OrderIntent(symbol=filled.symbol, side=opposite_side, price=target, amount=order_size)


def identify_stale_orders(
    open_orders: list[dict],
    current_levels: list[Decimal],
) -> list[str]:
    level_set = set(current_levels)
    stale_ids = []
    for order in open_orders:
        if Decimal(str(order["price"])) not in level_set:
            stale_ids.append(order["id"])
    return stale_ids
