# Binance Futures Grid Trading Bot

A Python CLI bot that executes arithmetic and geometric grid trading strategies on Binance USDT-M perpetual futures. Supports any CCXT futures symbol, paper trading on testnet, and walk-forward backtesting against historical data.

## Quick Start

```bash
# 1. Set up environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure
cp config/config.example.yaml config/config.yaml   # edit trading parameters
cp .env.example .env                                # add your Binance API keys

# 3. Validate
python run.py validate -c config/config.yaml

# 4. Paper trade on testnet
python run.py paper -c config/config.yaml

# 5. Backtest against historical data
python run.py backtest -c config/config.yaml --start 2025-01-01 --end 2025-03-01

# 6. Live trading (with confirmation)
python run.py live -c config/config.yaml
```

## Commands

| Command | Description |
|---------|-------------|
| `python run.py validate -c config.yaml` | Validate configuration file |
| `python run.py paper -c config.yaml` | Run on Binance testnet (no real funds) |
| `python run.py live -c config.yaml` | Run with real funds (confirms before start) |
| `python run.py backtest -c config.yaml --start DATE --end DATE` | Walk-forward simulation |
| `pytest tests/ -v -m "not integration"` | Run unit tests |
| `pytest tests/ -v -m integration` | Run integration tests (needs testnet keys) |
| `ruff check src/ tests/` | Lint |

## Architecture

```
binance-bot-trade/
├── config/              YAML configuration
├── src/
│   ├── config.py        Config dataclasses + YAML loader
│   ├── exchange.py      Async CCXT wrapper (testnet + live)
│   ├── grid_strategy.py Grid level math, order generation, rebalancing
│   ├── risk_manager.py  Position limits, stop-loss, price/quantity rounding
│   ├── data_fetcher.py  Paginated OHLCV fetching
│   ├── backtester.py    Walk-forward simulation engine
│   ├── bot.py           Main trading loop
│   └── cli.py           CLI argument parsing
├── tests/               Unit + integration tests
├── docs/decisions/      Architecture Decision Records
├── run.py               Entry point
└── requirements.txt
```

## Strategy Types

### Arithmetic Grid
Equal dollar spacing between levels. Best when price oscillates in a fixed dollar range.

```
Example: $90,000 – $110,000, 5 levels
Levels: [90000, 95000, 100000, 105000, 110000]
Step: $5,000 between each level
```

### Geometric Grid
Equal percentage spacing between levels. Best when price oscillates in percentage terms.

```
Example: $50,000 – $200,000, 5 levels
Levels: [50000, ~70711, ~100000, ~141421, 200000]
Ratio: ~1.414x between each level
```

## How Grid Trading Works

1. Define a price range (upper/lower) and number of grid levels
2. Place limit buy orders at all levels *below* current price
3. Place limit sell orders at all levels *above* current price
4. When a buy fills → place a sell at the next level up (captures profit)
5. When a sell fills → place a buy at the next level down
6. Profit is `order_size × grid_step` per completed pair

## Key Design Decisions

See `docs/decisions/` for detailed ADRs:

| ADR | Decision |
|-----|----------|
| [ADR-001](docs/decisions/adr-001-decimal-for-finance.md) | `Decimal` for all financial calculations (not `float`) |
| [ADR-002](docs/decisions/adr-002-python-ccxt.md) | Python + CCXT for exchange integration |
| [ADR-003](docs/decisions/adr-003-pure-strategy-functions.md) | Pure functions for strategy logic |
| [ADR-004](docs/decisions/adr-004-config-driven-symbol.md) | Config-driven symbol selection (any CCXT pair) |
| [ADR-005](docs/decisions/adr-005-polling-v1.md) | Polling over WebSocket for initial version |

## Configuration

```yaml
# config/config.yaml
symbol: BTC/USDT:USDT          # Any CCXT futures pair
grid:
  type: arithmetic             # or geometric
  upper_price: 110000.0
  lower_price: 90000.0
  grid_count: 10
  order_size: 0.001            # BTC per order
  leverage: 2
risk:
  max_position_btc: 0.01
  max_grid_count: 20
  stop_loss_pct: -5.0
backtest:
  trading_fee_pct: 0.04        # Taker fee rate
```

## Environment Variables

Set in `.env`:

```
BINANCE_API_KEY=              # For live trading
BINANCE_SECRET_KEY=
BINANCE_TESTNET_API_KEY=      # For paper trading
BINANCE_TESTNET_SECRET_KEY=
```
