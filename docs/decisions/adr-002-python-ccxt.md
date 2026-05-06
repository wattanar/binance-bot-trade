# ADR-002: Python + CCXT for Exchange Integration

## Status
Accepted

## Date
2026-05-06

## Context
We need to interact with Binance Futures API for order placement, order management, balance fetching, historical data retrieval, and real-time price monitoring. The bot must support both Binance testnet (paper trading) and Binance live.

## Decision
Use **CCXT 4.x** (async support) with **Python 3.10+**. CCXT provides a unified, tested, and maintained interface to 100+ exchanges including Binance Futures.

## Alternatives Considered

### Direct Binance REST + WebSocket (python-binance)
- Pros: Lighter dependency, Binance-specific optimizations
- Cons: Only supports Binance; would need rewrite to support other exchanges
- Rejected: CCXT handles rate limiting, error retries, and exchange-specific quirks that we'd need to reimplement

### Node.js + ccxt (TypeScript)
- Pros: Same CCXT benefits, static typing
- Cons: Fewer financial/data-science libraries for backtesting
- Rejected: Python ecosystem (pandas, numpy) is substantially better for backtesting and analysis

### Go + go-binance
- Pros: Compiled binary, low resource usage
- Cons: Smaller ecosystem for trading, no mature backtesting framework
- Rejected: Development speed and library availability favor Python for this use case

## Consequences
- `ccxt.async_support.binance` used for all exchange operations
- Testnet mode: `exchange.set_sandbox_mode(True)` with separate testnet API keys
- Rate limiting handled automatically by CCXT
- Symbol format: `BTC/USDT:USDT` (CCXT unified futures format) — works for any pair
- Introduction of `Exchange` wrapper class isolates CCXT from strategy/bot code
- Integration tests require testnet API keys and are marked with `@pytest.mark.integration`
