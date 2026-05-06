import argparse
import asyncio
import json
from datetime import datetime

from loguru import logger

from src.config import ConfigError, load_config
from src.data_fetcher import fetch_ohlcv
from src.exchange import Exchange
from src.backtester import run_backtest
from src.bot import run_bot


def cmd_validate(args) -> int:
    try:
        config = load_config(args.config)
        print("Config OK")
        print(f"  Symbol:     {config.symbol}")
        print(f"  Grid type:  {config.grid.grid_type.value}")
        print(f"  Range:      {float(config.grid.lower_price):.2f} - {float(config.grid.upper_price):.2f}")
        print(f"  Levels:     {config.grid.grid_count}")
        print(f"  Order size: {float(config.grid.order_size)} BTC")
        print(f"  Leverage:   {config.grid.leverage}x")
        print(f"  Max pos:    {float(config.risk.max_position_btc)} BTC")
        return 0
    except ConfigError as e:
        logger.error("Config error: {}", e)
        return 1


async def _run_backtest(args) -> int:
    try:
        config = load_config(args.config)
    except ConfigError as e:
        logger.error("Config error: {}", e)
        return 1

    api_key = args.api_key or ""
    secret = args.secret or ""

    if not api_key or not secret:
        logger.warning("No API keys provided. Backtest needs exchange for historical data.")
        logger.warning("Set --api-key and --secret flags or use BINANCE_API_KEY env.")
        return 1

    exchange = Exchange(api_key, secret, testnet=False)
    await exchange.connect()

    start_date = datetime.fromisoformat(args.start) if args.start else datetime(2025, 1, 1)
    end_date = datetime.fromisoformat(args.end) if args.end else datetime.now()

    logger.info("Fetching OHLCV data from {} to {}...", start_date.date(), end_date.date())
    df = await fetch_ohlcv(exchange, config.symbol, start_date, end_date, timeframe=args.timeframe or "1m")

    if df.empty:
        logger.error("No data fetched for the given date range")
        await exchange.close()
        return 1

    logger.info("Fetched {} candles", len(df))
    logger.info("Running backtest...")

    result = await run_backtest(config, df)

    print()
    print(result.summary_table())

    if args.output:
        output = {
            "total_pnl": float(result.total_pnl),
            "total_return_pct": float(result.total_return_pct),
            "sharpe_ratio": float(result.sharpe_ratio),
            "max_drawdown_pct": float(result.max_drawdown_pct),
            "trade_count": result.trade_count,
            "win_count": result.win_count,
            "losing_count": result.losing_count,
            "profit_factor": float(result.profit_factor),
        }
        with open(args.output, "w") as f:
            json.dump(output, f, indent=2)
        logger.info("Results saved to {}", args.output)

    await exchange.close()
    return 0


def cmd_backtest(args) -> int:
    return asyncio.run(_run_backtest(args))


def cmd_paper(args) -> int:
    try:
        config = load_config(args.config)
    except ConfigError as e:
        logger.error("Config error: {}", e)
        return 1

    asyncio.run(run_bot(config, mode="paper"))
    return 0


def cmd_live(args) -> int:
    print("╔══════════════════════════════════════════╗")
    print("║  WARNING: LIVE TRADING MODE              ║")
    print("║  This will use REAL funds.               ║")
    print("║  Type 'yes' to confirm:                  ║")
    print("╚══════════════════════════════════════════╝")

    confirmation = input("> ").strip()
    if confirmation.lower() != "yes":
        print("Aborted.")
        return 0

    try:
        config = load_config(args.config)
    except ConfigError as e:
        logger.error("Config error: {}", e)
        return 1

    asyncio.run(run_bot(config, mode="live"))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="binance-grid-bot",
        description="Binance Futures Grid Trading Bot",
    )
    sub = parser.add_subparsers(dest="command")

    validate_p = sub.add_parser("validate", help="Validate config file")
    validate_p.add_argument("--config", "-c", required=True, help="Path to config YAML")
    validate_p.set_defaults(func=cmd_validate)

    paper_p = sub.add_parser("paper", help="Run paper trading on testnet")
    paper_p.add_argument("--config", "-c", required=True, help="Path to config YAML")
    paper_p.set_defaults(func=cmd_paper)

    live_p = sub.add_parser("live", help="Run live trading")
    live_p.add_argument("--config", "-c", required=True, help="Path to config YAML")
    live_p.set_defaults(func=cmd_live)

    backtest_p = sub.add_parser("backtest", help="Run backtest")
    backtest_p.add_argument("--config", "-c", required=True, help="Path to config YAML")
    backtest_p.add_argument("--start", help="Start date (YYYY-MM-DD)")
    backtest_p.add_argument("--end", help="End date (YYYY-MM-DD)")
    backtest_p.add_argument("--timeframe", help="Candle timeframe (default: 1m)")
    backtest_p.add_argument("--output", "-o", help="Output JSON file for results")
    backtest_p.add_argument("--api-key", help="Binance API key (or use env var)")
    backtest_p.add_argument("--secret", help="Binance secret key (or use env var)")
    backtest_p.set_defaults(func=cmd_backtest)

    return parser
