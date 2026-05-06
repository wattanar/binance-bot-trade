from decimal import Decimal
from typing import Optional

import ccxt.async_support as ccxt_async
from loguru import logger


class ExchangeError(Exception):
    pass


class Exchange:
    def __init__(self, api_key: str, secret: str, testnet: bool = False):
        self._api_key = api_key
        self._secret = secret
        self._testnet = testnet
        self._exchange: Optional[ccxt_async.Exchange] = None

    def __repr__(self) -> str:
        return f"Exchange(testnet={self._testnet}, connected={self._exchange is not None})"

    def __str__(self) -> str:
        return self.__repr__()

    def __getstate__(self) -> dict:
        raise TypeError("Exchange objects cannot be pickled — contains credentials")

    def __setstate__(self, state: dict) -> None:
        raise TypeError("Exchange objects cannot be unpickled — contains credentials")

    async def connect(self) -> None:
        config: dict = {
            "apiKey": self._api_key,
            "secret": self._secret,
            "enableRateLimit": True,
            "options": {"defaultType": "future"},
        }

        if self._testnet:
            config["options"]["defaultType"] = "future"
            exchange_class = getattr(ccxt_async, "binanceusdm", None)
            if exchange_class is None:
                exchange_class = ccxt_async.binance

            self._exchange = exchange_class(config)
            self._exchange.set_sandbox_mode(True)
        else:
            self._exchange = ccxt_async.binance(config)

        await self._exchange.load_markets()
        logger.info(
            "Connected to Binance Futures {}",
            "testnet" if self._testnet else "live",
        )

    async def close(self) -> None:
        if self._exchange is not None:
            await self._exchange.close()
            self._exchange = None

    @property
    def _ex(self) -> ccxt_async.Exchange:
        if self._exchange is None:
            raise ExchangeError("Not connected. Call connect() first.")
        return self._exchange

    async def fetch_ticker(self, symbol: str) -> dict:
        return await self._ex.fetch_ticker(symbol)

    async def fetch_balance(self, asset: str = "USDT") -> Optional[Decimal]:
        balance = await self._ex.fetch_balance()
        free = balance.get(asset, {}).get("free", 0)
        return Decimal(str(free)) if free else Decimal("0")

    async def fetch_positions(self, symbol: Optional[str] = None) -> list[dict]:
        positions = await self._ex.fetch_positions(symbol)
        return positions or []

    async def fetch_open_orders(self, symbol: Optional[str] = None) -> list[dict]:
        orders = await self._ex.fetch_open_orders(symbol)
        return orders or []

    async def place_limit_order(
        self,
        symbol: str,
        side: str,
        amount: float | Decimal,
        price: float | Decimal,
    ) -> dict:
        amount_f = float(amount)
        price_f = float(price)
        logger.info("Placing {} limit order: {} {} @ {}", side, symbol, amount_f, price_f)
        order = await self._ex.create_limit_order(symbol, side, amount_f, price_f)
        logger.info("Order placed: id={} status={}", order.get("id"), order.get("status"))
        return order

    async def cancel_order(self, symbol: str, order_id: str) -> dict:
        logger.info("Cancelling order {} on {}", order_id, symbol)
        result = await self._ex.cancel_order(order_id, symbol)
        return result

    async def set_leverage(self, symbol: str, leverage: int) -> None:
        logger.info("Setting leverage for {} to {}x", symbol, leverage)
        await self._ex.set_leverage(leverage, symbol)

    async def fetch_exchange_info(self, symbol: Optional[str] = None) -> dict:
        markets = self._ex.markets
        if symbol and symbol in markets:
            return markets[symbol]
        return markets

    async def cancel_all_orders(self, symbol: Optional[str] = None) -> None:
        orders = await self.fetch_open_orders(symbol)
        for order in orders:
            await self.cancel_order(order["symbol"], order["id"])
        logger.info("Cancelled {} open orders", len(orders))
