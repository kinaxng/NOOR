from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PluginManifest:
    """Small compatibility model for recovered first-party plugins."""

    id: str
    name: str = ''
    version: str = ''
    type: str = 'tool'
    description: str = ''
    tags: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    enabled_by_default: bool = True
    config_schema: dict[str, Any] = field(default_factory=dict)
    default_config: dict[str, Any] = field(default_factory=dict)
    contributions: dict[str, Any] = field(default_factory=dict)
    frontend: dict[str, Any] = field(default_factory=dict)


@dataclass
class PluginTestResult:
    ok: bool
    message: str = ''
    details: dict[str, Any] = field(default_factory=dict)
