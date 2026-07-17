from __future__ import annotations

from datetime import datetime, timedelta

from epaper_dashboard.models import CalendarEvent, DashboardData, Departure, NewsItem, TaskItem


def load_placeholder_data() -> DashboardData:
    now = datetime.now().replace(second=0, microsecond=0)
    return DashboardData(
        calendar=[
            CalendarEvent(now + timedelta(hours=1), "Team sync"),
            CalendarEvent(now + timedelta(hours=3), "Dentist"),
            CalendarEvent(now + timedelta(days=1, hours=2), "Dinner with friends"),
        ],
        tasks=[
            TaskItem("Buy CR2450 batteries"),
            TaskItem("Check Nebular display resolution"),
            TaskItem("Prepare weekly meal plan", now + timedelta(days=1)),
        ],
        departures=[
            Departure("RE1", "Hauptbahnhof", now + timedelta(minutes=8), platform="2"),
            Departure("S3", "Airport", now + timedelta(minutes=14), delay_minutes=4, platform="4"),
            Departure("U8", "City center", now + timedelta(minutes=21), platform="1"),
        ],
        news=[
            NewsItem("Renderer scaffold is alive"),
            NewsItem("Next step: wire CalDAV calendar source"),
            NewsItem("Then add train departure provider"),
        ],
    )
