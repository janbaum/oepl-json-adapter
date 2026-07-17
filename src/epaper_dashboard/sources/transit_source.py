from __future__ import annotations

from datetime import datetime
from typing import Any

import requests
from dateutil import parser

from epaper_dashboard.models import DashboardData, Departure


def load_transit_data(config: dict[str, Any], dashboard: dict[str, Any]) -> DashboardData:
    provider = str(config.get("provider", "db_transport_rest"))
    if provider != "db_transport_rest":
        raise ValueError(f"Unsupported transit provider: {provider}")

    station_id = str(config.get("station_id", "")).strip()
    if not station_id:
        raise ValueError("sources.transit.station_id must be set when transit is enabled")

    limit = int(dashboard.get("sections", {}).get("transit", {}).get("max_items", 5))
    base_url = str(config.get("base_url", "https://v6.db.transport.rest")).rstrip("/")
    timeout = int(config.get("timeout_seconds", 20))
    params = _request_params(config, limit)

    response = requests.get(
        f"{base_url}/stops/{station_id}/departures",
        params=params,
        headers={"User-Agent": "epaper-dashboard/0.1"},
        timeout=timeout,
    )
    response.raise_for_status()

    departures = [_parse_departure(item) for item in response.json()]
    departures = [item for item in departures if item is not None]
    departures.sort(key=lambda item: item.time)
    return DashboardData(calendar=[], tasks=[], departures=departures[:limit], news=[])


def _request_params(config: dict[str, Any], limit: int) -> dict[str, str | int]:
    params: dict[str, str | int] = {
        "results": limit,
        "duration": int(config.get("duration_minutes", 60)),
        "language": str(config.get("language", "de")),
        "profile": str(config.get("profile", "dbnav")),
    }

    direction = str(config.get("direction", "")).strip()
    if direction:
        params["direction"] = direction

    for key, value in dict(config.get("products", {})).items():
        params[str(key)] = "true" if bool(value) else "false"

    return params


def _parse_departure(item: dict[str, Any]) -> Departure | None:
    when = item.get("when") or item.get("plannedWhen")
    if not when:
        return None

    line = item.get("line") or {}
    delay_seconds = item.get("delay") or 0
    delay_minutes = int(round(delay_seconds / 60))

    return Departure(
        line=str(line.get("name") or "?"),
        destination=str(item.get("direction") or "?"),
        time=_parse_time(str(when)),
        delay_minutes=delay_minutes,
        platform=item.get("platform") or item.get("plannedPlatform"),
        cancelled=bool(item.get("cancelled", False)),
    )


def _parse_time(value: str) -> datetime:
    parsed = parser.isoparse(value)
    return parsed if parsed.tzinfo else parsed.astimezone()
