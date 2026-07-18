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
MID = (150, 150, 150)
DARK = (85, 85, 85)
HEADER_H = 50
BODY_TOP = 66
TRAIN_ICON_W = 82


def render_dashboard(
    tag: TagConfig,
    title: str,
    data: DashboardData,
    output_path: Path,
    *,
    tag_status: TagStatus | None = None,
    show_battery: bool = True,
    layout: str = "overview",
    updated_at: datetime | None = None,
) -> Path:
    image = Image.new("RGB", (tag.width, tag.height), WHITE)
    draw = ImageDraw.Draw(image)

    fonts = Fonts()
    updated_at = updated_at or datetime.now()

    draw.rectangle((0, 0, tag.width, HEADER_H), fill=BLACK)
    title_x = 20
    draw.text((title_x, 8), title, font=fonts.title, fill=WHITE)

    battery_right = tag.width - 20
    battery_left = tag.width - 112
    separator_x = battery_left - 24
    time_right = separator_x - 24
    title_right = title_x + _text_width(draw, title, fonts.title)
    time_left = _header_time_left(draw, time_right, updated_at, fonts)
    icon_center = title_right + max(0, time_left - title_right) // 2
    _train_icon(draw, icon_center - TRAIN_ICON_W // 2, 12)
    _draw_header_time(draw, time_right, 11, updated_at, fonts)
    draw.line((separator_x, 9, separator_x, HEADER_H - 9), fill=LIGHT, width=1)
    if show_battery:
        _battery(draw, battery_left, 8, battery_right, tag_status, fonts)

    if layout == "transportation" or data.transit_groups:
        _transportation_body(draw, tag, data, fonts)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path, "JPEG", quality=95)
        return output_path

    gutter = 18
    top = BODY_TOP
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
    y = BODY_TOP
    row_h = 26
    group_gap = 10
    groups = data.transit_groups

    if data.errors:
        _section(draw, "Problems", gutter, y, tag.width - gutter * 2, tag.height - y - gutter, fonts)
        y += 42
        for error in data.errors[:5]:
            draw.text((gutter + 12, y), _clip(error, 70), font=fonts.small, fill=BLACK)
            y += row_h
        return

    if not groups:
        _section(draw, "Departures", gutter, y, tag.width - gutter * 2, tag.height - y - gutter, fonts)
        y += 42
        if not data.departures:
            draw.text((gutter + 12, y), "No connections", font=fonts.small, fill=BLACK)
            return
        for departure in data.departures[:10]:
            _transport_row(draw, departure, gutter + 12, y, tag.width - gutter * 2 - 24, fonts)
            y += row_h
        return

    for group in groups:
        if y > tag.height - 48:
            break

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
    platform = f"Gl. {departure.platform}" if departure.platform else ""
    time_text = departure.time.strftime("%H:%M")
    line_x = x + 68
    destination_x = x + 178
    line_text = _clip_to_width(draw, departure.line, destination_x - line_x - 8, fonts.small)

    platform_col_x = x + width - 132
    status_col_right = x + width - 6
    destination_width = max(120, platform_col_x - destination_x - 10)

    draw.text((x, y), time_text, font=fonts.small, fill=BLACK)
    draw.text((line_x, y), line_text, font=fonts.small, fill=BLACK)
    draw.text((destination_x, y), _clip_to_width(draw, departure.destination, destination_width, fonts.small), font=fonts.small, fill=BLACK)
    if platform:
        _draw_right(draw, platform, x + width - 54, y, fonts.small, BLACK)
    if status:
        _draw_right(draw, status, status_col_right, y, fonts.small_bold, BLACK)


class Fonts:
    def __init__(self) -> None:
        self.title = _font(30, bold=True)
        self.medium = _font(24, bold=True)
        self.section = _font(22, bold=True)
        self.small = _font(19)
        self.small_bold = _font(19, bold=True)
        self.battery = _font(14)
        self.battery_bold = _font(15, bold=True)
        self.tiny = _font(12)


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


def _train_icon(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    draw.line((x, y + 10, x + 13, y + 10), fill=DARK, width=2)
    draw.line((x + 6, y + 16, x + 22, y + 16), fill=MID, width=2)
    draw.line((x + 14, y + 22, x + 31, y + 22), fill=LIGHT, width=2)

    body = [
        (x + 28, y + 4),
        (x + 70, y + 4),
        (x + 82, y + 14),
        (x + 70, y + 24),
        (x + 28, y + 24),
    ]
    draw.polygon(body, outline=WHITE, fill=BLACK)
    draw.line((x + 28, y + 24, x + 70, y + 24), fill=WHITE, width=2)
    draw.line((x + 70, y + 4, x + 82, y + 14, x + 70, y + 24), fill=WHITE, width=2)

    draw.rectangle((x + 34, y + 8, x + 47, y + 15), outline=WHITE, width=2)
    draw.rectangle((x + 52, y + 8, x + 65, y + 15), outline=WHITE, width=2)
    draw.ellipse((x + 38, y + 21, x + 44, y + 27), outline=WHITE, width=2)
    draw.ellipse((x + 58, y + 21, x + 64, y + 27), outline=WHITE, width=2)


def _battery(
    draw: ImageDraw.ImageDraw,
    left: int,
    y: int,
    right: int,
    tag_status: TagStatus | None,
    fonts: Fonts,
) -> None:
    outline = (left, y + 8, left + 35, y + 25)
    draw.rectangle(outline, outline=WHITE, width=2)
    draw.rectangle((left + 36, y + 13, left + 39, y + 20), fill=WHITE)

    percent = _battery_percent(tag_status)
    if percent is not None:
        fill_width = max(2, int(29 * max(0, min(100, percent)) / 100))
        draw.rectangle((left + 3, y + 11, left + 3 + fill_width, y + 22), fill=WHITE)

    percent_label, voltage_label = _battery_labels(tag_status)
    _draw_right(draw, percent_label, right, y + 1, fonts.battery_bold, WHITE)
    _draw_right(draw, voltage_label, right, y + 20, fonts.battery, LIGHT)


def _battery_labels(tag_status: TagStatus | None) -> tuple[str, str]:
    if not tag_status:
        return "--%", "--V"
    percent = _battery_percent(tag_status)
    voltage = tag_status.battery_mv / 1000 if tag_status.battery_mv is not None else None
    percent_label = f"{percent}%" if percent is not None else "--%"
    voltage_label = f"{voltage:.2f}V" if voltage is not None else "--V"
    return percent_label, voltage_label


def _battery_percent(tag_status: TagStatus | None) -> int | None:
    if not tag_status:
        return None
    if tag_status.battery_percent is not None:
        return tag_status.battery_percent
    if tag_status.battery_mv is None:
        return None
    return _estimate_battery_percent(tag_status.battery_mv)


def _estimate_battery_percent(battery_mv: int) -> int:
    # Approximation for a 3V coin-cell style tag battery under light load.
    return max(0, min(100, round((battery_mv - 2400) / 600 * 100)))


def _clip(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 3] + "..."


def _clip_to_width(draw: ImageDraw.ImageDraw, value: str, max_width: int, font: ImageFont.ImageFont) -> str:
    if _text_width(draw, value, font) <= max_width:
        return value
    clipped = value
    while clipped and _text_width(draw, clipped + "...", font) > max_width:
        clipped = clipped[:-1]
    return clipped + "..." if clipped else "..."


def _draw_right(draw: ImageDraw.ImageDraw, value: str, right: int, y: int, font: ImageFont.ImageFont, fill: tuple[int, int, int]) -> None:
    draw.text((right - _text_width(draw, value, font), y), value, font=font, fill=fill)


def _draw_header_time(draw: ImageDraw.ImageDraw, right: int, y: int, updated_at: datetime, fonts: Fonts) -> None:
    start_x = _header_time_left(draw, right, updated_at, fonts)
    label = "last updated"
    time_text = updated_at.strftime("%H:%M")
    label_width = _text_width(draw, label, fonts.tiny)
    gap = 8
    draw.text((start_x, y + 11), label, font=fonts.tiny, fill=LIGHT)
    draw.text((start_x + label_width + gap, y), time_text, font=fonts.medium, fill=WHITE)


def _header_time_left(draw: ImageDraw.ImageDraw, right: int, updated_at: datetime, fonts: Fonts) -> int:
    label = "last updated"
    time_text = updated_at.strftime("%H:%M")
    label_width = _text_width(draw, label, fonts.tiny)
    time_width = _text_width(draw, time_text, fonts.medium)
    gap = 8
    return right - label_width - gap - time_width


def _text_width(draw: ImageDraw.ImageDraw, value: str, font: ImageFont.ImageFont) -> int:
    left, _, right, _ = draw.textbbox((0, 0), value, font=font)
    return right - left


def _departure_status(delay_minutes: int, cancelled: bool) -> str:
    if cancelled:
        return "X"
    if delay_minutes > 0:
        return f"+{delay_minutes}"
    if delay_minutes < 0:
        return str(delay_minutes)
    return ""
