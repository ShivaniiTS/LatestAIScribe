"""
mcp_servers/data/template_server.py — Note template loading.

Loads note templates from config/templates/ YAML files.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "config" / "templates"


class NoteTemplate:
    def __init__(self, data: dict[str, Any]):
        self.name = data.get("name", "")
        self.note_type = data.get("note_type", "SOAP")
        self.specialty = data.get("specialty", "general")
        self.sections = data.get("sections", [])
        self.source_file = data.get("source_file", "")

    def section_labels(self) -> list[str]:
        return [s["label"] for s in self.sections]


class TemplateServer:
    """Loads and caches note templates from YAML files."""

    def __init__(self, templates_dir: str | Path | None = None):
        self._dir = Path(templates_dir) if templates_dir else _TEMPLATES_DIR
        self._cache: dict[str, NoteTemplate] = {}

    def get_template(self, name: str) -> Optional[NoteTemplate]:
        if name in self._cache:
            return self._cache[name]

        path = self._dir / f"{name}.yaml"
        if not path.exists():
            logger.warning("template_server: template '%s' not found at %s", name, path)
            return None

        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}

        template = NoteTemplate(data)
        self._cache[name] = template
        return template

    def list_templates(self) -> list[str]:
        if not self._dir.exists():
            return []
        return [p.stem for p in self._dir.glob("*.yaml")]

    def get_for_specialty(self, specialty: str, note_type: str = "SOAP") -> Optional[NoteTemplate]:
        for name in self.list_templates():
            t = self.get_template(name)
            if t and t.specialty == specialty and t.note_type == note_type:
                return t
        return self.get_template("soap_default")


_server: Optional[TemplateServer] = None


def get_template_server() -> TemplateServer:
    global _server
    if _server is None:
        _server = TemplateServer()
    return _server
