"""
mcp_servers/llm/base.py — LLM Engine base interface.

All LLM backends implement LLMEngine. The note node calls only this interface.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional


@dataclass
class LLMMessage:
    role: str    # "system" | "user" | "assistant"
    content: str


@dataclass
class LLMConfig:
    """Per-request generation parameters."""
    model: str = "qwen2.5:14b"
    temperature: float = 0.1
    max_tokens: int = 4096
    top_p: float = 0.9
    stop: list[str] = field(default_factory=list)
    seed: Optional[int] = None
    response_format: Optional[dict] = None


@dataclass
class LLMResponse:
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    finish_reason: str = "stop"
    parsed_json: Optional[dict] = None


@dataclass
class LLMChunk:
    """Streaming response chunk."""
    delta: str
    is_final: bool
    finish_reason: Optional[str] = None


@dataclass
class ModelInfo:
    model_name: str
    context_window: int
    supports_streaming: bool = True
    supports_json_mode: bool = False
    capabilities: list[str] = field(default_factory=list)


class LLMEngine(ABC):
    """Abstract base class for all LLM engines."""

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        messages: list[LLMMessage],
        config: LLMConfig,
    ) -> LLMResponse:
        ...

    @abstractmethod
    async def generate_stream(
        self,
        system_prompt: str,
        messages: list[LLMMessage],
        config: LLMConfig,
    ) -> AsyncIterator[LLMChunk]:
        ...

    @abstractmethod
    async def get_model_info(self) -> ModelInfo:
        ...

    async def health_check(self) -> bool:
        try:
            await self.get_model_info()
            return True
        except Exception:
            return False

    @property
    def name(self) -> str:
        return self.__class__.__name__.replace("Server", "").lower()
