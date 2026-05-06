import asyncio
import os
import signal
from decimal import Decimal
from typing import Optional

from dotenv import load_dotenv
from loguru import logger

from src.config import BotConfig
from src.exchange import Exchange, ExchangeError
from src.grid_strategy import (
    OrderIntent,
    calculate_grid_levels,
    generate_initial_orders,
)
from src.risk_manager import validate_order, check_grid_limit, calculate_position_size


load_dotenv()


class GridTradingBot:
    def __init__(self, config: BotConfig, mode: str = "paper"):
        self.config = config
        self.mode = mode
        self.exchange: Optional[Exchange] = None
        self.running = False
        self.levels: list[Decimal] = []
        self.step: Decimal = Decimal("0")
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        testnet = self.mode == "paper"
        api_key = os.environ.get("BINANCE_TESTNET_API_KEY" if testnet else "BINANCE_API_KEY", "")
        secret = os.environ.get("BINANCE_TESTNET_SECRET_KEY" if testnet else "BINANCE_SECRET_KEY", "")

        if not api_key or not secret:
            raise ExchangeError(
                f"Missing API keys for {self.mode} mode. "
                f"Set BINANCE_{'TESTNET_' if testnet else ''}API_KEY and "
                f"BINANCE_{'TESTNET_' if testnet else ''}SECRET_KEY in .env"
            )

        self.exchange = Exchange(api_key, secret, testnet=testnet)
        await self.exchange.connect()

        self.levels = calculate_grid_levels(self.config.grid)
        self.step = (self.config.grid.upper_price - self.config.grid.lower_price) / (self.config.grid.grid_count - 1)

        await self.exchange.set_leverage(self.config.symbol, self.config.grid.leverage)

        await self.exchange.cancel_all_orders(self.config.symbol)

        ticker = await self.exchange.fetch_ticker(self.config.symbol)
        current_price = Decimal(str(ticker["last"]))

        logger.info("Grid: {} to {}, {} levels, step={:.2f}",
                    float(self.config.grid.lower_price),
                    float(self.config.grid.upper_price),
                    self.config.grid.grid_count,
                    float(self.step))
        logger.info("Current price: {:.2f}", float(current_price))

        initial_orders = generate_initial_orders(
            self.levels, current_price, self.config.grid.order_size, self.config.symbol
        )

        buy_count = sum(1 for o in initial_orders if o.side == "buy")
        sell_count = sum(1 for o in initial_orders if o.side == "sell")
        logger.info("Placing {} buy and {} sell orders", buy_count, sell_count)

        for order in initial_orders:
            positions = await self.exchange.fetch_positions(self.config.symbol)
            current_pos = calculate_position_size(positions)
            open_orders = await self.exchange.fetch_open_orders(self.config.symbol)

            if not validate_order(order, current_pos, self.config.risk):
                logger.warning("Rejected order: {} {} @ {}", order.side, order.amount, order.price)
                continue
            if not check_grid_limit(len(open_orders), self.config.risk):
                logger.warning("Grid limit reached, stopping order placement")
                break

            try:
                await self.exchange.place_limit_order(
                    symbol=order.symbol,
                    side=order.side,
                    amount=float(order.amount),
                    price=float(order.price),
                )
                await asyncio.sleep(0.2)
            except Exception as e:
                logger.error("Failed to place order: {}", e)

        self.running = True
        await self._main_loop()

    async def _main_loop(self) -> None:
        poll_interval = 5
        backoff = 1

        while self.running and not self._shutdown_event.is_set():
            try:
                await self._check_and_rebalance()

                ticker = await self.exchange.fetch_ticker(self.config.symbol)
                current_price = Decimal(str(ticker["last"]))

                if current_price < self.levels[0] or current_price > self.levels[-1]:
                    logger.warning(
                        "Price {:.2f} is outside grid range [{:.2f}, {:.2f}]",
                        float(current_price),
                        float(self.levels[0]),
                        float(self.levels[-1]),
                    )

                backoff = 1
                await asyncio.sleep(poll_interval)

            except Exception as e:
                logger.error("Error in main loop: {}", e)
                logger.info("Reconnecting in {}s...", backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)

    async def _check_and_rebalance(self) -> None:
        open_orders = await self.exchange.fetch_open_orders(self.config.symbol)
        positions = await self.exchange.fetch_positions(self.config.symbol)

        filled_order_ids = set()
        previous_state = getattr(self, "_previous_order_ids", set())
        current_order_ids = {o["id"] for o in open_orders}
        filled_order_ids = previous_state - current_order_ids
        self._previous_order_ids = current_order_ids

        for oid in filled_order_ids:
            logger.info("Order {} filled, rebalancing", oid)

        if filled_order_ids:
            for _ in filled_order_ids:
                for level in self.levels:
                    order_at_level = None
                    for o in open_orders:
                        if Decimal(str(o["price"])) == level:
                            order_at_level = o
                            break

                    if order_at_level is None:
                        adjacent_buy = level - self.step
                        adjacent_sell = level + self.step

                        has_buy_below = any(
                            Decimal(str(o["price"])) == adjacent_buy and o["side"] == "buy"
                            for o in open_orders
                        )
                        has_sell_above = any(
                            Decimal(str(o["price"])) == adjacent_sell and o["side"] == "sell"
                            for o in open_orders
                        )

                        if not has_sell_above and adjacent_sell <= self.levels[-1]:
                            order = OrderIntent(symbol=self.config.symbol, side="sell", price=level, amount=self.config.grid.order_size)
                            positions = await self.exchange.fetch_positions(self.config.symbol)
                            current_pos = calculate_position_size(positions)
                            if validate_order(order, current_pos, self.config.risk):
                                try:
                                    await self.exchange.place_limit_order(order.symbol, order.side, float(order.amount), float(order.price))
                                    await asyncio.sleep(0.2)
                                except Exception as e:
                                    logger.error("Rebalance order failed: {}", e)

                        if not has_buy_below and adjacent_buy >= self.levels[0]:
                            order = OrderIntent(symbol=self.config.symbol, side="buy", price=level, amount=self.config.grid.order_size)
                            positions = await self.exchange.fetch_positions(self.config.symbol)
                            current_pos = calculate_position_size(positions)
                            if validate_order(order, current_pos, self.config.risk):
                                try:
                                    await self.exchange.place_limit_order(order.symbol, order.side, float(order.amount), float(order.price))
                                    await asyncio.sleep(0.2)
                                except Exception as e:
                                    logger.error("Rebalance order failed: {}", e)

    async def shutdown(self) -> None:
        logger.info("Shutting down...")
        self.running = False
        self._shutdown_event.set()

        if self.exchange is not None:
            try:
                await self.exchange.cancel_all_orders(self.config.symbol)
                logger.info("All orders cancelled")
            except Exception as e:
                logger.error("Error cancelling orders: {}", e)
            finally:
                await self.exchange.close()


async def run_bot(config: BotConfig, mode: str = "paper") -> None:
    bot = GridTradingBot(config, mode)

    loop = asyncio.get_event_loop()

    def signal_handler():
        logger.info("Received shutdown signal")
        asyncio.ensure_future(bot.shutdown())

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            signal.signal(sig, lambda s, f: signal_handler())

    try:
        await bot.start()
    except Exception as e:
        logger.error("Bot error: {}", e)
        await bot.shutdown()
