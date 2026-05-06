# ADR-004: Config-Driven Symbol Selection

## Status
Accepted

## Date
2026-05-06

## Context
The bot could either hardcode `BTC/USDT:USDT` as the sole trading pair or support any CCXT-compatible futures symbol. Supporting multiple pairs from day one requires minimal extra code but significantly expands utility.

## Decision
Symbol is a YAML config field, not hardcoded. The bot accepts any valid CCXT futures symbol (e.g., `ETH/USDT:USDT`, `SOL/USDT:USDT`, `BNB/USDT:USDT`). The `Exchange` wrapper, strategy functions, and bot loop are all symbol-parameterized.

## Alternatives Considered

### Hardcoded BTC/USDT only
- Pros: Simpler config, no symbol validation needed
- Cons: Can't trade any other pair without code changes
- Rejected: CCXT already abstracts away exchange differences; parameterizing the symbol is trivially achievable

### Multi-pair bot (trade multiple pairs simultaneously)
- Pros: Diversification
- Cons: Significantly more complex state management, risk tracking, and config
- Rejected: Scoped for future ADR if needed. Current architecture supports it but the bot loop is single-pair.

## Consequences
- `config.yaml` `symbol` field can be any valid CCXT futures pair
- `GridConfig.symbol` property flows through to all exchange and strategy calls
- The config parser validates grid parameters regardless of symbol (grid range may need different values for ETH vs BTC, but same validation)
- Exchange wrapper `fetch_exchange_info(symbol)` returns symbol-specific lot size, tick size, and min notional for precision validation
- Geometric grid config validation checks `upper_price/lower_price > 1` (works for any pair)
