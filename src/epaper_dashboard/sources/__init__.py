"""Data source adapters."""

from __future__ import annotations

import logging
from typing import Any

from epaper_dashboard.models import DashboardData
from epaper_dashboard.sources.placeholder import load_placeholder_data

LOG = logging.getLogger(__name__)


def load_dashboard_data(sources: dict[str, Any], dashboard: dict[str, Any]) -> DashboardData:
    data = load_placeholder_data()
    sections = dict(dashboard.get("sections", {}))

    caldav_config = dict(sources.get("caldav", {}))
    if caldav_config.get("enabled"):
        try:
            from epaper_dashboard.sources.caldav_source import load_caldav_data

            caldav_data = load_caldav_data(caldav_config, dashboard)
            data = DashboardData(
                calendar=caldav_data.calendar or data.calendar,
                tasks=caldav_data.tasks or data.tasks,
                departures=data.departures,
                news=data.news,
                transit_groups=data.transit_groups,
            )
        except Exception:
            LOG.exception("Failed to load CalDAV data; using placeholder calendar/tasks")

    rss_config = dict(sources.get("rss", {}))
    if rss_config.get("enabled"):
        try:
            from epaper_dashboard.sources.rss_source import load_rss_data

            rss_data = load_rss_data(rss_config, dashboard)
            data = DashboardData(
                calendar=data.calendar,
                tasks=data.tasks,
                departures=data.departures,
                news=rss_data.news or data.news,
                transit_groups=data.transit_groups,
            )
        except Exception:
            LOG.exception("Failed to load RSS data; using placeholder news")

    transit_config = _transit_source_config(sources, dashboard)
    transit_enabled = bool(transit_config.get("enabled")) or bool(transit_config.get("directions"))
    if transit_enabled:
        try:
            from epaper_dashboard.sources.transit_source import load_transit_data

            transit_data = load_transit_data(transit_config, dashboard)
            data = DashboardData(
                calendar=data.calendar,
                tasks=data.tasks,
                departures=transit_data.departures or data.departures,
                news=data.news,
                transit_groups=transit_data.transit_groups,
            )
        except Exception:
            LOG.exception("Failed to load transit data; using placeholder departures")

    return data


def _transit_source_config(sources: dict[str, Any], dashboard: dict[str, Any]) -> dict[str, Any]:
    config = _dashboard_source_config(sources, dashboard, "transit")

    root_directions = sources.get("directions")
    if root_directions and not config.get("directions"):
        config["directions"] = root_directions

    directions_section = dict(dashboard.get("sections", {}).get("directions", {}))
    if directions_section.get("directions") and not config.get("directions"):
        config["directions"] = directions_section["directions"]
    if directions_section.get("enabled"):
        config["enabled"] = True
    if "max_items" in directions_section and "max_items" not in config:
        config["max_items"] = directions_section["max_items"]

    return config


def _dashboard_source_config(sources: dict[str, Any], dashboard: dict[str, Any], name: str) -> dict[str, Any]:
    config = dict(sources.get(name, {}))
    config.update(dict(dashboard.get("sources", {}).get(name, {})))

    section = dict(dashboard.get("sections", {}).get(name, {}))
    for key, value in section.items():
        if key != "enabled":
            config[key] = value

    return config
