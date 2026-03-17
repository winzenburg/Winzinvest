"""
Contract cache — resolve symbol → ConId once, cache for session lifetime.

The single source of truth for contract identity.  Every execution path
must resolve contracts through this cache rather than constructing
Stock(symbol, "SMART", "USD") inline.

This is one of the few modules permitted to import ib_insync.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from ib_insync import Contract, IB, Option, Stock

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Canonical contract record
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResolvedContract:
    """Immutable, fully-qualified contract identity.

    Once resolved, strategy and execution code reference this instead of
    raw symbol strings.  The frozen dataclass ensures nothing mutates it.
    """

    con_id: int
    symbol: str
    sec_type: str
    exchange: str
    primary_exchange: str
    currency: str
    ib_contract: Contract = field(repr=False, compare=False)

    @property
    def key(self) -> str:
        """Cache key: ConId is the canonical identifier."""
        return f"{self.con_id}@{self.exchange}"


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


class ContractCache:
    """Session-lifetime cache for resolved IBKR contracts.

    Usage::

        cache = ContractCache(ib)
        contract = await cache.resolve("NVDA")
        # contract.con_id is the canonical identifier
        # contract.ib_contract is the qualified ib_insync Contract

    Resolution happens at most once per symbol per session.  Repeated
    calls return the cached result with zero API chatter.
    """

    def __init__(self, ib: IB) -> None:
        self._ib = ib
        self._by_symbol: Dict[str, ResolvedContract] = {}
        self._by_con_id: Dict[int, ResolvedContract] = {}
        self._failed: Dict[str, float] = {}
        self._failure_cooldown_seconds = 300.0

    # -- Public API --------------------------------------------------------

    async def resolve(self, symbol: str, sec_type: str = "STK", currency: str = "USD") -> Optional[ResolvedContract]:
        """Resolve a symbol to a canonical ResolvedContract.

        Returns None if qualification fails (and cools down for 5 min
        before retrying the same symbol to avoid API chatter).
        """
        symbol = symbol.strip().upper()
        cache_key = f"{symbol}:{sec_type}:{currency}"

        cached = self._by_symbol.get(cache_key)
        if cached is not None:
            return cached

        if cache_key in self._failed:
            elapsed = time.monotonic() - self._failed[cache_key]
            if elapsed < self._failure_cooldown_seconds:
                logger.debug("Skipping %s — failed %.0fs ago (cooldown %.0fs)", cache_key, elapsed, self._failure_cooldown_seconds)
                return None
            del self._failed[cache_key]

        return await self._qualify_and_cache(symbol, sec_type, currency, cache_key)

    async def resolve_option(
        self,
        symbol: str,
        expiry: str,
        strike: float,
        right: str,
        currency: str = "USD",
    ) -> Optional[ResolvedContract]:
        """Resolve an option contract to a canonical ResolvedContract."""
        symbol = symbol.strip().upper()
        right = right.upper()
        cache_key = f"{symbol}:OPT:{expiry}:{strike}:{right}:{currency}"

        cached = self._by_symbol.get(cache_key)
        if cached is not None:
            return cached

        if cache_key in self._failed:
            elapsed = time.monotonic() - self._failed[cache_key]
            if elapsed < self._failure_cooldown_seconds:
                return None
            del self._failed[cache_key]

        return await self._qualify_option_and_cache(symbol, expiry, strike, right, currency, cache_key)

    def get_by_con_id(self, con_id: int) -> Optional[ResolvedContract]:
        """Look up a previously resolved contract by ConId."""
        return self._by_con_id.get(con_id)

    def get_by_symbol(self, symbol: str, sec_type: str = "STK", currency: str = "USD") -> Optional[ResolvedContract]:
        """Look up a previously resolved contract by symbol (no API call)."""
        cache_key = f"{symbol.strip().upper()}:{sec_type}:{currency}"
        return self._by_symbol.get(cache_key)

    async def resolve_many(self, symbols: Sequence[str], sec_type: str = "STK", currency: str = "USD") -> List[ResolvedContract]:
        """Resolve multiple symbols, returning only the successful ones."""
        results: List[ResolvedContract] = []
        for sym in symbols:
            resolved = await self.resolve(sym, sec_type, currency)
            if resolved is not None:
                results.append(resolved)
        return results

    @property
    def stats(self) -> Dict[str, int]:
        """Cache statistics for observability."""
        return {
            "cached_by_symbol": len(self._by_symbol),
            "cached_by_con_id": len(self._by_con_id),
            "failed_cooldown": len(self._failed),
        }

    def clear(self) -> None:
        """Clear the cache (e.g. on reconnect if contract state may have changed)."""
        self._by_symbol.clear()
        self._by_con_id.clear()
        self._failed.clear()
        logger.info("Contract cache cleared")

    # -- Internal ----------------------------------------------------------

    async def _qualify_and_cache(
        self, symbol: str, sec_type: str, currency: str, cache_key: str,
    ) -> Optional[ResolvedContract]:
        """Qualify a stock contract via the IBKR API and cache the result."""
        try:
            raw = Stock(symbol, "SMART", currency)
            qualified = await self._ib.qualifyContractsAsync(raw)
            if not qualified:
                logger.warning("Contract qualification failed: %s", symbol)
                self._failed[cache_key] = time.monotonic()
                return None

            contract = qualified[0]
            return self._store(contract, cache_key)

        except Exception as exc:
            logger.error("Contract resolution error for %s: %s", symbol, exc)
            self._failed[cache_key] = time.monotonic()
            return None

    async def _qualify_option_and_cache(
        self,
        symbol: str,
        expiry: str,
        strike: float,
        right: str,
        currency: str,
        cache_key: str,
    ) -> Optional[ResolvedContract]:
        """Qualify an option contract via the IBKR API and cache the result."""
        try:
            raw = Option(symbol, expiry, strike, right, "SMART", currency=currency)
            qualified = await self._ib.qualifyContractsAsync(raw)
            if not qualified:
                logger.warning("Option qualification failed: %s %s %s %s", symbol, expiry, strike, right)
                self._failed[cache_key] = time.monotonic()
                return None

            contract = qualified[0]
            return self._store(contract, cache_key)

        except Exception as exc:
            logger.error("Option resolution error for %s: %s", symbol, exc)
            self._failed[cache_key] = time.monotonic()
            return None

    def _store(self, contract: Contract, cache_key: str) -> ResolvedContract:
        """Wrap a qualified ib_insync Contract into a ResolvedContract and cache it."""
        resolved = ResolvedContract(
            con_id=contract.conId,
            symbol=contract.symbol,
            sec_type=contract.secType,
            exchange=contract.exchange,
            primary_exchange=getattr(contract, "primaryExchange", "") or "",
            currency=contract.currency,
            ib_contract=contract,
        )

        self._by_symbol[cache_key] = resolved
        self._by_con_id[resolved.con_id] = resolved

        logger.debug(
            "Cached contract: %s → ConId=%d exchange=%s",
            cache_key, resolved.con_id, resolved.exchange,
        )
        return resolved
