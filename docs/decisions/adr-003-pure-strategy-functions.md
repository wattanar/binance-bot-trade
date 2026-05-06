# ADR-003: Pure Functions for Strategy Logic

## Status
Accepted

## Date
2026-05-06

## Context
Grid trading strategy involves grid level calculation, order splitting (buys vs sells), rebalancing logic after fills, and stale order identification. These algorithms must be correct, testable, and reusable across paper trading, live trading, and backtesting modes.

## Decision
Implement all strategy logic as pure functions — no side effects, no exchange I/O, no mutable state. The bot loop handles state management (open orders, current levels) and calls strategy functions as needed. The `SimulatedExchange` for backtesting uses the same pure strategy functions as the live bot.

## Alternatives Considered

### Stateful strategy class
- Pros: Encapsulates grid state naturally
- Cons: Harder to test (must set up full state), couples state management to algorithm
- Rejected: Same algorithm needs to work in backtesting (simulated state) and live trading (exchange state). Pure functions compose better across contexts.

### Inline strategy in bot loop
- Pros: Less code, no function calls
- Cons: Can't unit test, can't reuse in backtester
- Rejected: Untestable strategy logic is a non-starter for financial code

## Consequences
- `src/grid_strategy.py` contains only pure functions: `calculate_grid_levels`, `split_levels_by_price`, `generate_initial_orders`, `rebalance_after_fill`, `identify_stale_orders`, `next_target_level`
- `src/risk_manager.py` follows same pattern: `validate_order`, `should_stop_loss`, `calculate_position_size`, `round_price`, `round_quantity`
- Backtester `SimulatedExchange.process_candle()` calls `rebalance_after_fill()` — same function as live bot
- Unit tests pass known inputs and assert exact outputs without mocks
- `OrderIntent` dataclass is the sole shared data structure between strategy and execution
