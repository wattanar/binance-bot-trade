# ADR-001: Use Decimal for All Financial Calculations

## Status
Accepted

## Date
2026-05-06

## Context
The trading bot performs arithmetic on prices (BTC/USDT), order quantities, profit calculations, and fee deductions. Using Python's native `float` type risks floating-point precision errors that compound across grid levels and trade executions.

## Decision
Use Python's `Decimal` type for all price, quantity, and financial ratio calculations throughout the codebase. `float` is only used at the boundary (converting to CCXT API parameters, since CCXT expects `float`).

## Alternatives Considered

### float
- Pros: Native Python type, fast, simpler syntax
- Cons: `0.1 + 0.2 != 0.3` — grid level spacing would drift with many levels
- Rejected: Unacceptable precision loss for financial calculations where exact cents matter

### int (satoshis/cents)
- Pros: Exact, fast, used by many exchange APIs internally
- Cons: Requires conversion at every boundary, easy to forget a conversion step
- Rejected: Adds complexity without benefit; CCXT handles conversion internally

## Consequences
- All `price`, `amount`, `step`, and ratio values are `Decimal`
- Config YAML values are parsed as strings then cast to `Decimal` to avoid float intermediate
- Rounding functions use explicit `ROUND_HALF_UP` (price) and `ROUND_DOWN` (quantity)
- Geometric grid ratio calculation requires float intermediate (for exponent) but last level is pinned to exact `upper_price` to prevent drift
- Tests use `Decimal("value")` literals throughout for precision guarantees
