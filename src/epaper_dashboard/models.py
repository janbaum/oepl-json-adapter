from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CalendarEvent:
    start: datetime
    title: str
    location: str | None = None


@dataclass(frozen=True)
class TaskItem:
    title: str
    due: datetime | None = None
    priority: int | None = None


@dataclass(frozen=True)
class Departure:
    line: str
    destination: str
    time: datetime
    delay_minutes: int = 0
    platform: str | None = None
    cancelled: bool = False


@dataclass(frozen=True)
class NewsItem:
    title: str
    source: str | None = None


@dataclass(frozen=True)
class TagStatus:
    battery_mv: int | None = None
    battery_percent: int | None = None
    rssi: int | None = None
    last_seen: str | None = None


@dataclass(frozen=True)
class DashboardData:
    calendar: list[CalendarEvent]
    tasks: list[TaskItem]
    departures: list[Departure]
    news: list[NewsItem]
