# Provider manager — YAML-backed CRUD for provider profiles
"""
config/provider_manager.py

YAML-backed CRUD for ProviderProfile objects.
Stores provider preferences (specialty, templates, vocabulary, quality tracking).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

import yaml

from orchestrator.state import ProviderProfile

logger = logging.getLogger(__name__)

_PROVIDERS_DIR = Path(__file__).parent / "providers"
_PROVIDERS_DIR.mkdir(exist_ok=True)


def _provider_file(provider_id: str) -> Path:
    return _PROVIDERS_DIR / f"{provider_id}.yaml"


def load_provider(provider_id: str) -> Optional[ProviderProfile]:
    path = _provider_file(provider_id)
    if not path.exists():
        return None
    with open(path, "r") as f:
        data = yaml.safe_load(f) or {}
    return ProviderProfile(**data)


def save_provider(profile: ProviderProfile) -> None:
    path = _provider_file(profile.provider_id)
    with open(path, "w") as f:
        yaml.dump(profile.model_dump(mode="json"), f, default_flow_style=False, sort_keys=False)
    logger.info("provider_manager: saved %s", profile.provider_id)


def list_providers() -> list[ProviderProfile]:
    providers = []
    for path in _PROVIDERS_DIR.glob("*.yaml"):
        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}
        try:
            providers.append(ProviderProfile(**data))
        except Exception as e:
            logger.warning("Failed to load provider %s: %s", path.name, e)
    return providers


def delete_provider(provider_id: str) -> bool:
    path = _provider_file(provider_id)
    if path.exists():
        path.unlink()
        logger.info("provider_manager: deleted %s", provider_id)
        return True
    return False


def create_provider(
    provider_id: str,
    name: str,
    specialty: str = "general",
    **kwargs: Any,
) -> ProviderProfile:
    profile = ProviderProfile(
        provider_id=provider_id,
        name=name,
        specialty=specialty,
        **kwargs,
    )
    save_provider(profile)
    return profile
