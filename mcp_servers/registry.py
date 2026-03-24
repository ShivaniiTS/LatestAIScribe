"""
mcp_servers/registry.py — Central engine discovery, instantiation, and health checking.

All engine selection is driven by config/engines.yaml.
Nodes call ``get_registry().get("llm")`` instead of importing servers directly.
"""
from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass, field
from typing import Any, Optional, Union

from config.loader import get_asr_config, get_llm_config, load_engines_config
from mcp_servers.asr.base import ASREngine
from mcp_servers.llm.base import LLMEngine
from mcp_servers.ehr.base import EHRAdapter

log = logging.getLogger(__name__)

EngineBase = Union[ASREngine, LLMEngine, EHRAdapter]

_SERVER_MAP: dict[tuple[str, str], tuple[str, str]] = {
    ("asr", "whisperx"): ("mcp_servers.asr.whisperx_server", "WhisperXServer"),
    ("asr", "faster_whisper"): ("mcp_servers.asr.faster_whisper_server", "FasterWhisperServer"),
    ("asr", "faster-whisper"): ("mcp_servers.asr.faster_whisper_server", "FasterWhisperServer"),
    ("llm", "ollama"): ("mcp_servers.llm.ollama_server", "OllamaServer"),
    ("ehr", "stub"): ("mcp_servers.ehr.stub_server", "StubEHRServer"),
    ("ehr", "manual"): ("mcp_servers.ehr.stub_server", "StubEHRServer"),
}


@dataclass
class EngineStatus:
    engine_type: str
    server_name: str
    healthy: bool
    error: Optional[str] = None


@dataclass
class RegistryStatus:
    engines: list[EngineStatus] = field(default_factory=list)

    @property
    def all_healthy(self) -> bool:
        return all(e.healthy for e in self.engines)

    def summary(self) -> str:
        lines = ["=== ENGINE REGISTRY STATUS ==="]
        for e in self.engines:
            icon = "OK" if e.healthy else "FAIL"
            line = f"  [{icon}] {e.engine_type}/{e.server_name}"
            if e.error:
                line += f" — {e.error}"
            lines.append(line)
        return "\n".join(lines)


class EngineRegistry:
    """Central registry for all MCP engine servers."""

    def __init__(self) -> None:
        self._config = load_engines_config()
        self._cache: dict[tuple[str, str], EngineBase] = {}

    def reload_config(self) -> None:
        from config.loader import invalidate_config_cache
        invalidate_config_cache()
        self._config = load_engines_config()
        self._cache.clear()

    def get(self, engine_type: str, server_name: Optional[str] = None) -> EngineBase:
        name = server_name or self._default_server(engine_type)
        cache_key = (engine_type, name)
        if cache_key not in self._cache:
            self._cache[cache_key] = self._instantiate(engine_type, name)
            log.info("registry: instantiated %s/%s", engine_type, name)
        return self._cache[cache_key]

    def get_llm(self, server_name: Optional[str] = None) -> LLMEngine:
        return self.get("llm", server_name)  # type: ignore

    def get_asr(self, server_name: Optional[str] = None) -> ASREngine:
        return self.get("asr", server_name)  # type: ignore

    def get_ehr(self, server_name: Optional[str] = None) -> EHRAdapter:
        return self.get("ehr", server_name)  # type: ignore

    async def health_check(self, engine_type: str, server_name: Optional[str] = None) -> EngineStatus:
        name = server_name or self._default_server(engine_type)
        try:
            engine = self.get(engine_type, name)
            healthy = await engine.health_check()
            return EngineStatus(engine_type, name, healthy, None if healthy else "health_check returned False")
        except Exception as exc:
            return EngineStatus(engine_type, name, False, str(exc))

    async def health_check_all(self) -> RegistryStatus:
        status = RegistryStatus()
        for (engine_type, name) in list(self._cache.keys()):
            result = await self.health_check(engine_type, name)
            status.engines.append(result)
        return status

    async def health_check_defaults(self) -> RegistryStatus:
        status = RegistryStatus()
        for engine_type in ("llm", "asr", "ehr"):
            try:
                name = self._default_server(engine_type)
                result = await self.health_check(engine_type, name)
                status.engines.append(result)
            except KeyError:
                status.engines.append(EngineStatus(engine_type, "(not configured)", False, "not configured"))
        return status

    def get_with_failover(self, engine_type: str, server_name: Optional[str] = None) -> EngineBase:
        name = server_name or self._default_server(engine_type)
        servers = self._configured_servers(engine_type)
        try:
            return self.get(engine_type, name)
        except Exception as exc:
            log.warning("registry: %s/%s failed: %s", engine_type, name, exc)
        for fallback in servers:
            if fallback == name:
                continue
            try:
                engine = self.get(engine_type, fallback)
                log.info("registry: failover %s/%s → %s", engine_type, name, fallback)
                return engine
            except Exception as exc:
                log.warning("registry: failover %s/%s also failed: %s", engine_type, fallback, exc)
        raise RuntimeError(f"No available {engine_type} engine")

    def unload_engine(self, engine_type: str, server_name: str | None = None) -> None:
        name = server_name or self._default_server(engine_type)
        cache_key = (engine_type, name)
        engine = self._cache.pop(cache_key, None)
        if engine is None:
            return
        if hasattr(engine, "unload_model"):
            engine.unload_model()
        log.info("registry: unloaded %s/%s", engine_type, name)

    def list_configured(self, engine_type: str) -> list[str]:
        return self._configured_servers(engine_type)

    # ── Internals ────────────────────────────────────────────────────────

    def _default_server(self, engine_type: str) -> str:
        section = self._config.get(engine_type, {})
        return (
            section.get("default_server")
            or section.get("default_adapter")
            or next(iter(self._configured_servers(engine_type)), "")
        )

    def _configured_servers(self, engine_type: str) -> list[str]:
        section = self._config.get(engine_type, {})
        servers = section.get("servers") or section.get("adapters") or {}
        return list(servers.keys())

    def _server_config(self, engine_type: str, server_name: str) -> dict[str, Any]:
        section = self._config.get(engine_type, {})
        servers = section.get("servers") or section.get("adapters") or {}
        if server_name not in servers:
            raise KeyError(f"Server '{server_name}' not found in engines.yaml [{engine_type}]")
        return {"name": server_name, **servers[server_name]}

    def _instantiate(self, engine_type: str, server_name: str) -> EngineBase:
        cfg = self._server_config(engine_type, server_name)
        server_type = cfg.get("type", server_name)
        map_key = (engine_type, server_type)
        if map_key not in _SERVER_MAP:
            raise KeyError(f"No implementation for {engine_type}/{server_type}")
        module_path, class_name = _SERVER_MAP[map_key]
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        return cls.from_config(cfg)


_registry: Optional[EngineRegistry] = None


def get_registry() -> EngineRegistry:
    global _registry
    if _registry is None:
        _registry = EngineRegistry()
    return _registry


def reset_registry() -> None:
    global _registry
    _registry = None
