from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from epaper_dashboard.config import TagConfig
from epaper_dashboard.models import DashboardData, TagStatus

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
