"""
mcp_servers/ehr/base.py — EHR adapter interface.

Provides patient context from electronic health records.
Default: stub adapter that returns empty context.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class EHRAdapter(ABC):
    """Abstract base class for EHR integrations."""

    @abstractmethod
    def get_patient_context(self, patient_id: str) -> dict[str, Any]:
        """Load patient demographics, history, and encounter context."""
        ...

    @abstractmethod
    def search_patients(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search for patients by name, MRN, or DOB."""
        ...

    async def health_check(self) -> bool:
        return True

    @property
    def name(self) -> str:
        return self.__class__.__name__.replace("Server", "").lower()


class StubEHRServer(EHRAdapter):
    """Default stub EHR adapter that returns empty context."""

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> "StubEHRServer":
        return cls()

    def get_patient_context(self, patient_id: str) -> dict[str, Any]:
        return {
            "demographics": {
                "patient_id": patient_id,
                "name": "",
                "age": None,
                "sex": "",
            },
            "encounter": {},
            "history": {
                "conditions": [],
                "medications": [],
                "allergies": [],
            },
        }

    def search_patients(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        return []
