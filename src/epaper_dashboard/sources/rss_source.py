from __future__ import annotations

from datetime import datetime
from time import mktime
from typing import Any

from dateutil import tz

from epaper_dashboard.models import DashboardData, NewsItem


def load_rss_data(config: dict[str, Any], dashboard: dict[str, Any]) -> DashboardData:
    import feedparser
    import requests

    limit = int(dashboard.get("sections", {}).get("news", {}).get("max_items", 4))
    timeout = int(config.get("timeout_seconds", 20))
    feeds = [_feed_config(item) for item in config.get("urls", [])]
    items: list[_ParsedNewsItem] = []

    for feed in feeds:
        response = requests.get(feed.url, headers={"User-Agent": "epaper-dashboard/0.1"}, timeout=timeout)
        response.raise_for_status()
        parsed = feedparser.parse(response.content)
        source = feed.source or parsed.feed.get("title")
        for entry in parsed.entries:
            title = str(entry.get("title", "")).strip()
            if not title:
                continue
            published = _published_at(entry)
            items.append(_ParsedNewsItem(title=title, source=source, published=published))

    items.sort(key=lambda item: item.published or datetime.min.replace(tzinfo=tz.UTC), reverse=True)
    news = [NewsItem(title=item.title, source=item.source) for item in items[:limit]]
    return DashboardData(calendar=[], tasks=[], departures=[], news=news)


class _FeedConfig:
    def __init__(self, url: str, source: str | None) -> None:
        self.url = url
        self.source = source


class _ParsedNewsItem:
    def __init__(self, title: str, source: str | None, published: datetime | None) -> None:
        self.title = title
        self.source = source
        self.published = published


def _feed_config(value: Any) -> _FeedConfig:
    if isinstance(value, str):
        return _FeedConfig(url=value, source=None)
    return _FeedConfig(url=str(value["url"]), source=value.get("source"))


def _published_at(entry: Any) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    return datetime.fromtimestamp(mktime(parsed), tz.UTC)
