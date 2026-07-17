"""Data source adapters."""

from __future__ import annotations

import logging
from typing import Any

from epaper_dashboard.models import DashboardData
from epaper_dashboard.sources.placeholder import load_placeholder_data

LOG = logging.getLogger(__name__)


def load_dashboard_data(sources: dict[str, Any], dashboard: dict[str, Any]) -> DashboardData:
    data = load_placeholder_data()

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
            )
        except Exception:
            LOG.exception("Failed to load RSS data; using placeholder news")

    transit_config = dict(sources.get("transit", {}))
    if transit_config.get("enabled"):
        try:
            from epaper_dashboard.sources.transit_source import load_transit_data

            transit_data = load_transit_data(transit_config, dashboard)
            data = DashboardData(
                calendar=data.calendar,
                tasks=data.tasks,
                departures=transit_data.departures or data.departures,
                news=data.news,
            )
        except Exception:
            LOG.exception("Failed to load transit data; using placeholder departures")

    return data
