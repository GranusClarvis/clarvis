"""Host adapter base interfaces for Clarvis extraction readiness."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class AdapterResult:
    host: str
    ok: bool
    data: Any
    message: str = ""


class HostAdapter(ABC):
    """Minimal host adapter interface for memory/context portability."""

    host: str

    @abstractmethod
    def store_memory(
        self,
        text: str,
        *,
        importance: float = 0.8,
        category: str = "clarvis-memories",
    ) -> AdapterResult:
        raise NotImplementedError

    @abstractmethod
    def search_memory(
        self,
        query: str,
        *,
        n: int = 5,
        collections: list[str] | None = None,
    ) -> AdapterResult:
        raise NotImplementedError

    @abstractmethod
    def build_context(
        self,
        task: str,
        *,
        tier: str = "standard",
    ) -> AdapterResult:
        raise NotImplementedError
