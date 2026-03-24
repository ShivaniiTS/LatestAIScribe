"""
tests/test_config.py — Tests for configuration loading.
"""
import os
from pathlib import Path


def test_load_engines_config():
    from config.loader import load_engines_config
    cfg = load_engines_config()
    assert cfg is not None
    assert "llm" in cfg or "asr" in cfg or "server" in cfg


def test_get_llm_config():
    from config.loader import get_llm_config
    cfg = get_llm_config()
    assert cfg is not None


def test_get_asr_config():
    from config.loader import get_asr_config
    cfg = get_asr_config()
    assert cfg is not None


def test_load_prompt():
    from config.loader import load_prompt
    prompt = load_prompt("note_generation")
    assert prompt is not None


def test_provider_manager(tmp_path):
    from config.provider_manager import create_provider, load_provider, list_providers, delete_provider
    # Temporarily override providers dir
    import config.provider_manager as pm
    original_dir = pm._PROVIDERS_DIR
    pm._PROVIDERS_DIR = tmp_path / "providers"
    pm._PROVIDERS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        profile = create_provider("test_doc", "Test Doctor", "general")
        assert profile.provider_id == "test_doc"

        p = load_provider("test_doc")
        assert p is not None
        assert p.name == "Test Doctor"

        providers = list_providers()
        assert len(providers) >= 1

        delete_provider("test_doc")
        p2 = load_provider("test_doc")
        assert p2 is None
    finally:
        pm._PROVIDERS_DIR = original_dir
