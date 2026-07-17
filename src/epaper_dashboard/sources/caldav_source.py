from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from typing import Any
from urllib.parse import urljoin
from xml.etree import ElementTree

import recurring_ical_events
import requests
from dateutil import tz
from icalendar import Calendar

from epaper_dashboard.models import CalendarEvent, DashboardData, TaskItem

LOG = logging.getLogger(__name__)

NS = {
    "d": "DAV:",
    "c": "urn:ietf:params:xml:ns:caldav",
    "cs": "http://calendarserver.org/ns/",
}


def load_caldav_data(config: dict[str, Any], dashboard: dict[str, Any]) -> DashboardData:
    client = CalDavClient(
        base_url=str(config["url"]),
        username=str(config["username"]),
        password=str(config["password"]),
    )

    days_ahead = int(config.get("days_ahead", 14))
    timezone_name = str(dashboard.get("timezone", "Europe/Berlin"))
    timezone = tz.gettz(timezone_name) or tz.UTC
    now = datetime.now(timezone)
    until = now + timedelta(days=days_ahead)

    calendar_urls = [str(url) for url in config.get("calendar_urls", [])]
    task_urls = [str(url) for url in config.get("task_urls", [])]

    if config.get("discover", True) and not calendar_urls and not task_urls:
        discovered = client.discover_collections()
        calendar_urls = discovered.calendar_urls
        task_urls = discovered.task_urls

    calendar_limit = int(dashboard.get("sections", {}).get("calendar", {}).get("max_items", 5))
    task_limit = int(dashboard.get("sections", {}).get("tasks", {}).get("max_items", 5))

    events = client.fetch_events(calendar_urls, now, until, timezone)[:calendar_limit]
    tasks = client.fetch_tasks(task_urls, timezone)[:task_limit]

    return DashboardData(calendar=events, tasks=tasks, departures=[], news=[])


class CollectionDiscovery:
    def __init__(self, calendar_urls: list[str], task_urls: list[str]) -> None:
        self.calendar_urls = calendar_urls
        self.task_urls = task_urls


class CalDavClient:
    def __init__(self, base_url: str, username: str, password: str) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.session = requests.Session()
        self.session.auth = (username, password)
        self.session.headers.update({"User-Agent": "epaper-dashboard/0.1"})

    def discover_collections(self) -> CollectionDiscovery:
        principal_url = self._current_user_principal()
        home_url = self._calendar_home_set(principal_url)
        calendar_urls: list[str] = []
        task_urls: list[str] = []

        body = """<?xml version="1.0" encoding="utf-8" ?>
<d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
  <d:prop>
    <d:displayname />
    <c:supported-calendar-component-set />
  </d:prop>
</d:propfind>"""
        root = self._request_xml("PROPFIND", home_url, body, depth="1")

        for response in root.findall("d:response", NS):
            href = _text(response.find("d:href", NS))
            if not href:
                continue
            components = {
                comp.attrib.get("name", "").upper()
                for comp in response.findall(".//c:supported-calendar-component-set/c:comp", NS)
            }
            collection_url = urljoin(self.base_url, href)
            if "VEVENT" in components:
                calendar_urls.append(collection_url)
            if "VTODO" in components:
                task_urls.append(collection_url)

        LOG.info("Discovered %d calendar collection(s), %d task collection(s)", len(calendar_urls), len(task_urls))
        return CollectionDiscovery(calendar_urls=calendar_urls, task_urls=task_urls)

    def fetch_events(
        self,
        collection_urls: list[str],
        start: datetime,
        end: datetime,
        timezone: tz.tzfile | tz.tzutc,
    ) -> list[CalendarEvent]:
        events: list[CalendarEvent] = []
        for collection_url in collection_urls:
            for calendar in self._query_collection(collection_url, "VEVENT", start, end):
                expanded = recurring_ical_events.of(calendar).between(start, end)
                for component in expanded:
                    summary = _component_text(component, "SUMMARY", "Untitled")
                    location = _component_text(component, "LOCATION", None)
                    dtstart = _component_datetime(component.get("DTSTART").dt, timezone)
                    if dtstart >= start:
                        events.append(CalendarEvent(start=dtstart, title=summary, location=location))

        events.sort(key=lambda event: event.start)
        return events

    def fetch_tasks(self, collection_urls: list[str], timezone: tz.tzfile | tz.tzutc) -> list[TaskItem]:
        tasks: list[TaskItem] = []
        for collection_url in collection_urls:
            for calendar in self._query_collection(collection_url, "VTODO"):
                for component in calendar.walk("VTODO"):
                    status = _component_text(component, "STATUS", "").upper()
                    if status == "COMPLETED":
                        continue
                    title = _component_text(component, "SUMMARY", "Untitled task")
                    due_property = component.get("DUE")
                    due = _component_datetime(due_property.dt, timezone) if due_property else None
                    priority_property = component.get("PRIORITY")
                    priority = int(priority_property) if priority_property else None
                    tasks.append(TaskItem(title=title, due=due, priority=priority))

        tasks.sort(key=lambda task: (task.due is None, task.due or datetime.max.replace(tzinfo=timezone), task.priority or 99))
        return tasks

    def _current_user_principal(self) -> str:
        body = """<?xml version="1.0" encoding="utf-8" ?>
<d:propfind xmlns:d="DAV:">
  <d:prop><d:current-user-principal /></d:prop>
</d:propfind>"""
        root = self._request_xml("PROPFIND", self.base_url, body, depth="0")
        href = _text(root.find(".//d:current-user-principal/d:href", NS))
        if not href:
            raise RuntimeError("CalDAV server did not return current-user-principal")
        return urljoin(self.base_url, href)

    def _calendar_home_set(self, principal_url: str) -> str:
        body = """<?xml version="1.0" encoding="utf-8" ?>
<d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
  <d:prop><c:calendar-home-set /></d:prop>
</d:propfind>"""
        root = self._request_xml("PROPFIND", principal_url, body, depth="0")
        href = _text(root.find(".//c:calendar-home-set/d:href", NS))
        if not href:
            raise RuntimeError("CalDAV server did not return calendar-home-set")
        return urljoin(self.base_url, href)

    def _query_collection(
        self,
        collection_url: str,
        component: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Calendar]:
        time_range = ""
        if start and end:
            time_range = f'<c:time-range start="{_caldav_time(start)}" end="{_caldav_time(end)}" />'

        body = f"""<?xml version="1.0" encoding="utf-8" ?>
<c:calendar-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
  <d:prop><c:calendar-data /></d:prop>
  <c:filter>
    <c:comp-filter name="VCALENDAR">
      <c:comp-filter name="{component}">
        {time_range}
      </c:comp-filter>
    </c:comp-filter>
  </c:filter>
</c:calendar-query>"""

        root = self._request_xml("REPORT", collection_url, body, depth="1")
        calendars = []
        for item in root.findall(".//c:calendar-data", NS):
            if item.text:
                calendars.append(Calendar.from_ical(item.text))
        return calendars

    def _request_xml(self, method: str, url: str, body: str, *, depth: str) -> ElementTree.Element:
        response = self.session.request(
            method,
            url,
            data=body.encode("utf-8"),
            headers={"Content-Type": "application/xml; charset=utf-8", "Depth": depth},
            timeout=30,
        )
        response.raise_for_status()
        return ElementTree.fromstring(response.content)


def _component_text(component: Any, key: str, default: str | None) -> str | None:
    value = component.get(key)
    return str(value) if value is not None else default


def _component_datetime(value: datetime | date, timezone: tz.tzfile | tz.tzutc) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone)
    return datetime.combine(value, time.min, tzinfo=timezone)


def _caldav_time(value: datetime) -> str:
    return value.astimezone(tz.UTC).strftime("%Y%m%dT%H%M%SZ")


def _text(element: ElementTree.Element | None) -> str | None:
    if element is None or element.text is None:
        return None
    return element.text.strip()
