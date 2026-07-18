from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from epaper_dashboard.config import TagConfig
from epaper_dashboard.models import DashboardData, Departure, TagStatus

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
YELLOW = (236, 205, 0)
LIGHT = (235, 235, 235)


def render_dashboard(
    tag: TagConfig,
    title: str,
    data: DashboardData,
    output_path: Path,
    *,
    tag_status: TagStatus | None = None,
    show_battery: bool = True,
    layout: str = "overview",
) -> Path:
    image = Image.new("RGB", (tag.width, tag.height), WHITE)
    draw = ImageDraw.Draw(image)

    fonts = Fonts()
    now = datetime.now().strftime("%H:%M")

    draw.rectangle((0, 0, tag.width, 58), fill=BLACK)
    draw.text((22, 13), title, font=fonts.title, fill=WHITE)
    draw.text((tag.width - 105, 17), now, font=fonts.medium, fill=WHITE)
    if show_battery:
        _battery(draw, max(tag.width - 315, tag.width // 2), 18, tag_status, fonts)

    if layout == "transportation" or data.transit_groups:
        _transportation_body(draw, tag, data, fonts)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path, "JPEG", quality=95)
        return output_path

    gutter = 18
    top = 76
    half = (tag.width - gutter * 3) // 2
    left_x = gutter
    right_x = gutter * 2 + half
    panel_h = (tag.height - top - gutter * 2) // 2

    _section(draw, "Calendar", left_x, top, half, panel_h, fonts)
    y = top + 42
    for event in data.calendar[:5]:
        draw.text((left_x + 12, y), event.start.strftime("%H:%M"), font=fonts.small_bold, fill=BLACK)
        draw.text((left_x + 85, y), _clip(event.title, 34), font=fonts.small, fill=BLACK)
        y += 29

    _section(draw, "Tasks", right_x, top, half, panel_h, fonts)
    y = top + 42
    for task in data.tasks[:5]:
        due = task.due.strftime("%d.%m") if task.due else "--"
        draw.text((right_x + 12, y), due, font=fonts.small_bold, fill=BLACK)
        draw.text((right_x + 85, y), _clip(task.title, 34), font=fonts.small, fill=BLACK)
        y += 29

    bottom = top + panel_h + gutter
    _section(draw, "Departures", left_x, bottom, half, panel_h, fonts)
    y = bottom + 42
    for dep in data.departures[:5]:
        color = YELLOW if dep.delay_minutes > 0 or dep.cancelled else WHITE
        draw.rectangle((left_x + 8, y - 2, left_x + half - 8, y + 24), fill=color)
        status = _departure_status(dep.delay_minutes, dep.cancelled)
        text = f"{dep.time.strftime('%H:%M')}  {dep.line}  {_clip(dep.destination, 21)} {status}"
        draw.text((left_x + 12, y), text, font=fonts.small, fill=BLACK)
        y += 29

    _section(draw, "News", right_x, bottom, half, panel_h, fonts)
    y = bottom + 42
    for item in data.news[:4]:
        draw.text((right_x + 12, y), _clip(item.title, 39), font=fonts.small, fill=BLACK)
        y += 33

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, "JPEG", quality=95)
    return output_path


def _transportation_body(draw: ImageDraw.ImageDraw, tag: TagConfig, data: DashboardData, fonts: Fonts) -> None:
    gutter = 18
    y = 76
    row_h = 26
    group_gap = 10
    current_origin = None
    groups = data.transit_groups

    if not groups:
        _section(draw, "Departures", gutter, y, tag.width - gutter * 2, tag.height - y - gutter, fonts)
        y += 42
        for departure in data.departures[:10]:
            _transport_row(draw, departure, gutter + 12, y, tag.width - gutter * 2 - 24, fonts)
            y += row_h
        return

    for group in groups:
        if y > tag.height - 48:
            break

        if group.origin != current_origin:
            draw.text((gutter, y), _clip(group.origin, 52), font=fonts.section, fill=BLACK)
            y += 29
            current_origin = group.origin

        draw.rectangle((gutter, y, tag.width - gutter, y + 28), fill=LIGHT)
        draw.text((gutter + 10, y + 3), _clip(group.title, 58), font=fonts.small_bold, fill=BLACK)
        y += 34

        if not group.departures:
            draw.text((gutter + 18, y), "No connections", font=fonts.small, fill=BLACK)
            y += row_h
        else:
            for departure in group.departures:
                if y > tag.height - 28:
                    break
                _transport_row(draw, departure, gutter + 18, y, tag.width - gutter * 2 - 18, fonts)
                y += row_h
        y += group_gap


def _transport_row(
    draw: ImageDraw.ImageDraw,
    departure: Departure,
    x: int,
    y: int,
    width: int,
    fonts: Fonts,
) -> None:
    delayed = departure.delay_minutes > 0 or departure.cancelled
    if delayed:
        draw.rectangle((x - 4, y - 1, x + width, y + 23), fill=YELLOW)

    status = _departure_status(departure.delay_minutes, departure.cancelled)
    platform = f" Gl. {departure.platform}" if departure.platform else ""
    text = f"{departure.time.strftime('%H:%M')}  {departure.line}  {_clip(departure.destination, 33)}{platform} {status}"
    draw.text((x, y), text, font=fonts.small, fill=BLACK)


class Fonts:
    def __init__(self) -> None:
        self.title = _font(34, bold=True)
        self.medium = _font(26, bold=True)
        self.section = _font(22, bold=True)
        self.small = _font(19)
        self.small_bold = _font(19, bold=True)


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    try:
        return ImageFont.truetype(name, size=size)
    except OSError:
        return ImageFont.load_default()


def _section(draw: ImageDraw.ImageDraw, title: str, x: int, y: int, w: int, h: int, fonts: Fonts) -> None:
    draw.rectangle((x, y, x + w, y + h), outline=BLACK, width=2)
    draw.rectangle((x, y, x + w, y + 32), fill=LIGHT)
    draw.text((x + 10, y + 4), title, font=fonts.section, fill=BLACK)


def _battery(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    tag_status: TagStatus | None,
    fonts: Fonts,
) -> None:
    label = _battery_label(tag_status)
    outline = (x, y + 4, x + 42, y + 22)
    draw.rectangle(outline, outline=WHITE, width=2)
    draw.rectangle((x + 43, y + 9, x + 47, y + 17), fill=WHITE)

    percent = tag_status.battery_percent if tag_status else None
    if percent is not None:
        fill_width = max(2, int(36 * max(0, min(100, percent)) / 100))
        draw.rectangle((x + 3, y + 7, x + 3 + fill_width, y + 19), fill=WHITE)

    draw.text((x + 55, y), label, font=fonts.small, fill=WHITE)


def _battery_label(tag_status: TagStatus | None) -> str:
    if not tag_status:
        return "BAT --"
    if tag_status.battery_percent is not None:
        return f"BAT {tag_status.battery_percent}%"
    if tag_status.battery_mv is not None:
        return f"BAT {tag_status.battery_mv / 1000:.2f}V"
    return "BAT --"


def _clip(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 3] + "..."


def _departure_status(delay_minutes: int, cancelled: bool) -> str:
    if cancelled:
        return "X"
    if delay_minutes > 0:
        return f"+{delay_minutes}"
    if delay_minutes < 0:
        return str(delay_minutes)
    return ""
