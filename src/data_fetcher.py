from datetime import datetime, timezone

import pandas as pd

from src.exchange import Exchange


async def fetch_ohlcv(
    exchange: Exchange,
    symbol: str,
    start_date: datetime,
    end_date: datetime,
    timeframe: str = "1m",
) -> pd.DataFrame:
    since_ms = int(start_date.timestamp() * 1000)
    end_ms = int(end_date.timestamp() * 1000)

    all_candles = []
    current_since = since_ms

    while current_since < end_ms:
        candles = await exchange._ex.fetch_ohlcv(
            symbol,
            timeframe=timeframe,
            since=current_since,
            limit=1000,
        )

        if not candles:
            break

        all_candles.extend(candles)

        last_timestamp = candles[-1][0]
        if last_timestamp <= current_since:
            current_since += _timeframe_to_ms(timeframe)
        else:
            current_since = last_timestamp + _timeframe_to_ms(timeframe)

    if not all_candles:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

    df = pd.DataFrame(all_candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)

    df = df[df["timestamp"] <= pd.Timestamp(end_date, tz=timezone.utc)]
    df = df.reset_index(drop=True)

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)

    return df


def _timeframe_to_ms(timeframe: str) -> int:
    unit = timeframe[-1]
    value = int(timeframe[:-1])
    multipliers = {"m": 60_000, "h": 3_600_000, "d": 86_400_000, "w": 604_800_000}
    return value * multipliers.get(unit, 60_000)
