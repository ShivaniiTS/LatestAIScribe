"""
Load and access engine/prompt configuration from YAML files.
All engine selection is driven by config/engines.yaml — never hardcoded.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_PROJECT_ROOT = Path(__file__).parent.parent
_ENGINES_PATH = _PROJECT_ROOT / "config" / "engines.yaml"
_PROMPTS_DIR = _PROJECT_ROOT / "config" / "prompts"


@lru_cache(maxsize=1)
def load_engines_config(path: str | None = None) -> dict[str, Any]:
    """Load config/engines.yaml and return as a nested dict (cached)."""
    target = Path(path) if path else _ENGINES_PATH
    with open(target) as f:
        return yaml.safe_load(f)


def invalidate_config_cache() -> None:
    """Force re-read of engines.yaml on next access."""
    load_engines_config.cache_clear()


def get_llm_config(server_name: str | None = None) -> dict[str, Any]:
    cfg = load_engines_config()
    llm_cfg = cfg["llm"]
    name = server_name or llm_cfg["default_server"]
    return {"name": name, **llm_cfg["servers"][name]}


def get_asr_config(server_name: str | None = None) -> dict[str, Any]:
    cfg = load_engines_config()
    asr_cfg = cfg["asr"]
    name = server_name or asr_cfg["default_server"]
    return {"name": name, **asr_cfg["servers"][name]}


@lru_cache(maxsize=16)
def load_prompt(prompt_name: str) -> dict[str, Any]:
    """Load a prompt YAML file from config/prompts/."""
    path = _PROMPTS_DIR / f"{prompt_name}.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


def resolve_env(value: str) -> str:
    """Resolve $ENV_VAR references."""
    if value.startswith("$"):
        return os.environ.get(value[1:], "")
    return value
