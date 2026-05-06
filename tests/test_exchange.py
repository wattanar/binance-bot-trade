import os

import pytest

from src.exchange import Exchange


pytestmark = pytest.mark.integration

TESTNET_API_KEY = os.environ.get("BINANCE_TESTNET_API_KEY", "")
TESTNET_SECRET = os.environ.get("BINANCE_TESTNET_SECRET_KEY", "")

requires_testnet = pytest.mark.skipif(
    not (TESTNET_API_KEY and TESTNET_SECRET),
    reason="BINANCE_TESTNET_API_KEY and BINANCE_TESTNET_SECRET_KEY not set",
)


@requires_testnet
class TestExchangeTestnet:
    @pytest.fixture
    async def exchange(self):
        ex = Exchange(TESTNET_API_KEY, TESTNET_SECRET, testnet=True)
        await ex.connect()
        yield ex
        await ex.close()

    @pytest.mark.asyncio
    async def test_connect_testnet(self):
        ex = Exchange(TESTNET_API_KEY, TESTNET_SECRET, testnet=True)
        try:
            await ex.connect()
            assert ex._exchange is not None
        finally:
            await ex.close()

    @pytest.mark.asyncio
    async def test_fetch_ticker(self, exchange):
        ticker = await exchange.fetch_ticker("BTC/USDT:USDT")
        assert "last" in ticker
        assert ticker["last"] > 0

    @pytest.mark.asyncio
    async def test_fetch_ticker_different_symbol(self, exchange):
        ticker = await exchange.fetch_ticker("ETH/USDT:USDT")
        assert "last" in ticker
        assert ticker["last"] > 0

    @pytest.mark.asyncio
    async def test_fetch_balance(self, exchange):
        balance = await exchange.fetch_balance("USDT")
        assert balance is not None

    @pytest.mark.asyncio
    async def test_fetch_positions(self, exchange):
        positions = await exchange.fetch_positions("BTC/USDT:USDT")
        assert isinstance(positions, list)

    @pytest.mark.asyncio
    async def test_set_leverage(self, exchange):
        await exchange.set_leverage("BTC/USDT:USDT", 2)

    @pytest.mark.asyncio
    async def test_fetch_open_orders(self, exchange):
        orders = await exchange.fetch_open_orders("BTC/USDT:USDT")
        assert isinstance(orders, list)

    @pytest.mark.asyncio
    async def test_place_and_cancel_order(self, exchange):
        ticker = await exchange.fetch_ticker("BTC/USDT:USDT")
        far_below = ticker["last"] * 0.5

        order = await exchange.place_limit_order(
            symbol="BTC/USDT:USDT",
            side="buy",
            amount=0.001,
            price=far_below,
        )
        assert order is not None
        assert "id" in order

        cancelled = await exchange.cancel_order("BTC/USDT:USDT", order["id"])
        assert cancelled is not None
