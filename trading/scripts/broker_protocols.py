"""
Structural protocols for broker objects used by signal/gate modules.

These protocols let gate and signal code accept any broker instance that
exposes the required interface, without importing ib_insync directly.
"""

from __future__ import annotations

from typing import Protocol, Sequence, runtime_checkable


@runtime_checkable
class PortfolioItem(Protocol):
    """Minimal shape of a portfolio item returned by ib.portfolio()."""

    @property
    def contract(self) -> object: ...
    @property
    def marketValue(self) -> float: ...


@runtime_checkable
class PositionItem(Protocol):
    """Minimal shape of a position returned by ib.positions()."""

    @property
    def contract(self) -> object: ...
    @property
    def position(self) -> float: ...


@runtime_checkable
class BrokerClient(Protocol):
    """Structural protocol for an IB-like broker client.

    Gate modules only need portfolio() and positions(); execution modules
    use much more of the API and can import ib_insync directly.
    """

    def isConnected(self) -> bool: ...
    def portfolio(self) -> Sequence[PortfolioItem]: ...
    def positions(self) -> Sequence[PositionItem]: ...
