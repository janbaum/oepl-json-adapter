from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


@dataclass(frozen=True)
class TagConfig:
    name: str
    mac: str
    width: int
    height: int
    color: str
    dither: bool
    lut: str | None
    refresh_seconds: int
    dashboard: str


@dataclass(frozen=True)
class AppConfig:
    ap_base_url: str
    tags: list[TagConfig]
    dashboards: dict[str, Any]
    sources: dict[str, Any]
    efficiency: dict[str, Any]
    data_dir: Path


def load_config() -> AppConfig:
    config_path = Path(os.environ.get("EPAPER_CONFIG", "config/config.yaml"))
    data_dir = Path(os.environ.get("EPAPER_DATA_DIR", "/data"))

    with config_path.open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file) or {}
    raw = _expand_env(raw)

    tags = [
        TagConfig(
            name=str(item["name"]),
            mac=str(item["mac"]),
            width=int(item["width"]),
            height=int(item["height"]),
            color=str(item.get("color", "bwy")),
            dither=bool(item.get("dither", False)),
            lut=str(item["lut"]) if item.get("lut") else None,
            refresh_seconds=int(item.get("refresh_seconds", 900)),
            dashboard=str(item.get("dashboard", "overview")),
        )
        for item in raw.get("tags", [])
    ]

    if not tags:
        raise ValueError("At least one tag must be configured in config.yaml")

    return AppConfig(
        ap_base_url=str(raw["ap"]["base_url"]).rstrip("/"),
        tags=tags,
        dashboards=dict(raw.get("dashboards", {})),
        sources=dict(raw.get("sources", {})),
        efficiency=dict(raw.get("efficiency", {})),
        data_dir=data_dir,
    )


def _expand_env(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _expand_env(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand_env(item) for item in value]
    if isinstance(value, str):
        return ENV_PATTERN.sub(lambda match: os.environ.get(match.group(1), ""), value)
    return value
