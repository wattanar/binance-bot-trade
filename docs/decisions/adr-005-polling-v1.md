# ADR-005: Polling Over WebSocket for Initial Version

## Status
Accepted (review after v1)

## Date
2026-05-06

## Context
The bot needs to detect when grid orders are filled to trigger rebalancing (place matching opposite-side order). Two approaches exist: WebSocket user data stream (real-time fill events) or REST polling (periodic `fetch_open_orders()` calls).

## Decision
Use REST polling (5-second interval) with exponential backoff for reconnection. WebSocket is planned for v2.

## Alternatives Considered

### Binance WebSocket User Data Stream
- Pros: Instant fill detection, no polling overhead, canonical approach for production bots
- Cons: Must maintain listenKey (refresh every 60 min), handle stream disconnections, more complex error handling
- Rejected for v1: Polling is simpler to implement correctly and suffices for grid trading where fills happen over minutes/hours, not milliseconds

### Polling at high frequency (1s)
- Pros: Faster fill detection
- Cons: Hits rate limits, wastes API calls
- Rejected: Grid trading doesn't need sub-second fill detection

### Polling at low frequency (30s+)
- Pros: Minimal API usage
- Cons: Could miss fills if price moves quickly through multiple levels
- Rejected: 5s is a good balance for BTC volatility

## Consequences
- `GridTradingBot._main_loop()` polls `fetch_open_orders()` every 5 seconds
- Fill detection: compare current open order IDs to previous poll's IDs; missing IDs = filled
- Reconnection: exponential backoff from 1s to 60s on errors
- Revisit this ADR if tight spreads or high volatility require faster fill detection
- WebSocket upgrade path: add `src/websocket.py` with listenKey management, swap bot loop to event-driven
