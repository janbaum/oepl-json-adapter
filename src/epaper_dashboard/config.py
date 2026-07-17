from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class TagConfig:
    name: str
    mac: str
    width: int
    height: int
    color: str
    dither: bool
    refresh_seconds: int
    dashboard: str


@dataclass(frozen=True)
class AppConfig:
    ap_base_url: str
    tags: list[TagConfig]
    dashboards: dict[str, Any]
    sources: dict[str, Any]
    data_dir: Path


def load_config() -> AppConfig:
    config_path = Path(os.environ.get("EPAPER_CONFIG", "config/config.yaml"))
    data_dir = Path(os.environ.get("EPAPER_DATA_DIR", "/data"))

    with config_path.open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file) or {}

    tags = [
        TagConfig(
            name=str(item["name"]),
            mac=str(item["mac"]),
            width=int(item["width"]),
            height=int(item["height"]),
            color=str(item.get("color", "bwy")),
            dither=bool(item.get("dither", False)),
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
        data_dir=data_dir,
    )
