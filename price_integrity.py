"""Price-source and trading-date integrity helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True)
class PriceQuote:
    price: float
    source: str
    as_of_date: date


def to_float(value: Any) -> float | None:
    """Convert provider numbers, including Turkish-formatted strings."""
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None

    normalized = value.strip().replace(' ', '')
    if not normalized:
        return None
    if ',' in normalized:
        normalized = normalized.replace('.', '').replace(',', '.')
    try:
        return float(normalized)
    except ValueError:
        return None


def parse_provider_date(value: Any) -> date | None:
    """Parse the date formats currently returned by market providers."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None

    raw = value.strip()
    if not raw:
        return None

    for candidate in (raw, raw.split()[0], raw[:10]):
        for pattern in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(candidate, pattern).date()
            except ValueError:
                pass
    return None


def same_price_series(previous_source: Any, current_source: Any) -> bool:
    """Only prices produced by the same provider form a comparable series."""
    return (
        isinstance(previous_source, str)
        and bool(previous_source)
        and previous_source == current_source
    )


def extract_bigpara_quotes(value: Any, symbol: str) -> list[PriceQuote]:
    """Extract dated quotes only from records for the exact symbol."""
    quotes: list[PriceQuote] = []
    if isinstance(value, dict):
        normalized = {str(key).lower(): child for key, child in value.items()}
        response_symbol = str(normalized.get('sembol', '')).upper()
        provider_date = parse_provider_date(normalized.get('tarih'))
        if response_symbol == symbol.upper() and provider_date is not None:
            for key in ('kapanis', 'son', 'fiyat'):
                price = to_float(normalized.get(key))
                if price is not None and price > 0:
                    quotes.append(PriceQuote(price, 'bigpara', provider_date))
                    break
        for child in value.values():
            quotes.extend(extract_bigpara_quotes(child, symbol))
    elif isinstance(value, list):
        for child in value:
            quotes.extend(extract_bigpara_quotes(child, symbol))
    return quotes
