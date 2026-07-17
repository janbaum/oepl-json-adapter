from __future__ import annotations

from pathlib import Path
from typing import Any

import requests

from epaper_dashboard.models import TagStatus


class OpenEPaperLinkClient:
    def __init__(self, base_url: str, timeout_seconds: int = 60) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def upload_image(self, mac: str, image_path: Path, *, dither: bool, lut: str | None = None) -> None:
        data = {"mac": mac, "dither": "1" if dither else "0"}
        if lut:
            data["lut"] = lut

        with image_path.open("rb") as file:
            response = requests.post(
                f"{self.base_url}/imgupload",
                data=data,
                files={"file": file},
                timeout=self.timeout_seconds,
            )
        response.raise_for_status()

    def get_tag_status(self, mac: str) -> TagStatus | None:
        response = requests.get(f"{self.base_url}/get_db", timeout=20)
        response.raise_for_status()
        tag = _find_tag(response.json(), mac)
        if not tag:
            return None
        return TagStatus(
            battery_mv=_battery_mv(tag),
            battery_percent=_percent(tag),
            rssi=_first_int(tag, ["rssi"]),
            last_seen=_first_str(tag, ["last_seen", "lastSeen", "lastseen"]),
        )


def _find_tag(value: Any, mac: str) -> dict[str, Any] | None:
    wanted = _normalize_mac(mac)
    if isinstance(value, dict):
        candidate_mac = _first_str(value, ["mac", "id", "addr", "address"])
        if candidate_mac and _normalize_mac(candidate_mac) == wanted:
            return value
        for key, item in value.items():
            if _normalize_mac(str(key)) == wanted and isinstance(item, dict):
                return item
            found = _find_tag(item, mac)
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = _find_tag(item, mac)
            if found:
                return found
    return None


def _normalize_mac(value: str) -> str:
    return "".join(char for char in value.lower() if char in "0123456789abcdef")


def _first_int(value: dict[str, Any], keys: list[str]) -> int | None:
    for key in keys:
        if key in value and value[key] not in (None, ""):
            try:
                return int(float(str(value[key]).rstrip("%")))
            except (TypeError, ValueError):
                return None
    return None


def _first_str(value: dict[str, Any], keys: list[str]) -> str | None:
    for key in keys:
        if key in value and value[key] not in (None, ""):
            return str(value[key])
    return None


def _battery_mv(value: dict[str, Any]) -> int | None:
    mv = _first_int(value, ["battery_mv", "batteryMv", "batteryVoltageMv", "batMv"])
    if mv is not None:
        return mv

    raw = _first_float(value, ["battery", "batteryVoltage", "bat", "voltage"])
    if raw is None:
        return None
    return int(raw * 1000) if raw < 20 else int(raw)


def _percent(value: dict[str, Any]) -> int | None:
    percent = _first_int(value, ["battery_percent", "batteryPercent", "battery_pct", "batPercent", "batPct"])
    if percent is None:
        return None
    return max(0, min(100, percent))


def _first_float(value: dict[str, Any], keys: list[str]) -> float | None:
    for key in keys:
        if key in value and value[key] not in (None, ""):
            try:
                return float(str(value[key]).rstrip("%"))
            except (TypeError, ValueError):
                return None
    return None
