from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN

from src.config import RiskConfig
from src.grid_strategy import OrderIntent


def validate_order(
    order: OrderIntent,
    current_position: Decimal,
    risk: RiskConfig,
) -> bool:
    if order.side == "buy":
        new_position = current_position + order.amount
        if new_position > risk.max_position_btc:
            return False
    return True


def check_grid_limit(open_orders_count: int, risk: RiskConfig) -> bool:
    return open_orders_count <= risk.max_grid_count


def should_stop_loss(current_pnl_pct: Decimal, risk: RiskConfig) -> bool:
    return current_pnl_pct <= risk.stop_loss_pct


def calculate_position_size(positions: list[dict]) -> Decimal:
    total = Decimal("0")
    for position in positions:
        contracts = Decimal(str(position.get("contracts", 0)))
        total += abs(contracts)
    return total


def round_price(price: Decimal, tick_size: Decimal) -> Decimal:
    return (price / tick_size).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * tick_size


def round_quantity(quantity: Decimal, step_size: Decimal) -> Decimal:
    return (quantity / step_size).quantize(Decimal("1"), rounding=ROUND_DOWN) * step_size
