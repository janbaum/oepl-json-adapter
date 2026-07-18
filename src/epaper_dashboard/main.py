from __future__ import annotations

import argparse
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from epaper_dashboard.config import AppConfig, TagConfig, load_config
from epaper_dashboard.fingerprint import content_digest
from epaper_dashboard.render import render_dashboard
from epaper_dashboard.sources import load_dashboard_data
from epaper_dashboard.upload import OpenEPaperLinkClient

LOG = logging.getLogger(__name__)


def main() -> None:
    args = _parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = load_config()
    config.data_dir.mkdir(parents=True, exist_ok=True)
    client = OpenEPaperLinkClient(config.ap_base_url)

    LOG.info("Starting epaper dashboard renderer for %d tag(s)", len(config.tags))
    if args.no_upload:
        LOG.info("No-upload mode enabled; images will be rendered but not sent to the AP")

    options = RuntimeOptions(once=args.once, no_upload=args.no_upload, force_render=args.force_render)
    next_runs = {tag.name: 0.0 for tag in config.tags}

    while True:
        now = time.monotonic()
        for tag in config.tags:
            if now < next_runs[tag.name]:
                continue
            try:
                _process_tag(config, client, tag, options)
            except Exception:
                LOG.exception("Failed to update tag %s", tag.name)
            finally:
                next_runs[tag.name] = time.monotonic() + tag.refresh_seconds

        if options.once:
            return

        sleep_for = _next_sleep(next_runs)
        LOG.info("Sleeping for %s seconds", sleep_for)
        time.sleep(sleep_for)


@dataclass(frozen=True)
class RuntimeOptions:
    once: bool = False
    no_upload: bool = False
    force_render: bool = False


def _process_tag(config: AppConfig, client: OpenEPaperLinkClient, tag: TagConfig, options: RuntimeOptions) -> None:
    dashboard = config.dashboards.get(tag.dashboard, {})
    title = str(dashboard.get("title", tag.name))
    data = load_dashboard_data(config.sources, dashboard)
    layout = _dashboard_layout(tag, dashboard)
    rendering_config = dict(dashboard.get("rendering", {}))
    show_battery = bool(rendering_config.get("show_battery", True))
    digest = content_digest(
        data,
        {
            "dashboard": tag.dashboard,
            "title": title,
            "layout": layout,
            "width": tag.width,
            "height": tag.height,
            "show_battery": show_battery,
        },
    )
    state_path = config.data_dir / f"{tag.name}.content.sha256"
    previous_digest = state_path.read_text(encoding="utf-8").strip() if state_path.exists() else ""

    if (
        not options.force_render
        and config.efficiency.get("upload_only_on_content_change", True)
        and digest == previous_digest
    ):
        LOG.info("Skipping %s; dashboard content unchanged", tag.name)
        return

    tag_status = None
    if show_battery:
        try:
            tag_status = client.get_tag_status(tag.mac)
        except Exception:
            LOG.exception("Failed to read battery status for %s", tag.name)

    image_path = config.data_dir / f"{tag.name}.jpg"
    render_dashboard(
        tag,
        title,
        data,
        image_path,
        tag_status=tag_status,
        show_battery=show_battery,
        layout=layout,
        updated_at=_dashboard_time(dashboard),
    )

    if (
        data.errors
        and not options.no_upload
        and config.efficiency.get("skip_upload_on_source_error", True)
    ):
        LOG.warning("Rendered %s for %s, but upload skipped because source errors are present", image_path, tag.name)
        return

    if options.no_upload:
        LOG.info("Rendered %s for %s; upload skipped by no-upload mode", image_path, tag.name)
        return

    LOG.info("Uploading %s to %s", image_path, tag.name)
    client.upload_image(tag.mac, image_path, dither=tag.dither, lut=tag.lut)
    state_path.write_text(digest, encoding="utf-8")


def _next_sleep(next_runs: dict[str, float]) -> int:
    next_due = min(next_runs.values())
    return max(5, int(next_due - time.monotonic()))


def _dashboard_layout(tag: TagConfig, dashboard: dict) -> str:
    configured = dashboard.get("layout")
    if configured:
        return str(configured)

    sections = dict(dashboard.get("sections", {}))
    transit_section = dict(sections.get("transit", {}))
    directions_section = dict(sections.get("directions", {}))
    if tag.dashboard == "transportation" or transit_section.get("directions") or directions_section.get("enabled"):
        return "transportation"

    return "overview"


def _dashboard_time(dashboard: dict) -> datetime:
    timezone_name = str(dashboard.get("timezone", "")).strip()
    if timezone_name:
        try:
            return datetime.now(ZoneInfo(timezone_name))
        except ZoneInfoNotFoundError:
            LOG.warning("Unknown dashboard timezone %s; using local time", timezone_name)
    return datetime.now()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render and upload OpenEPaperLink dashboard images")
    parser.add_argument("--once", action="store_true", help="run one update cycle and exit")
    parser.add_argument("--no-upload", action="store_true", help="render images without uploading them to the AP")
    parser.add_argument(
        "--force-render",
        action="store_true",
        help="render even when the content fingerprint has not changed",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="shortcut for --once --no-upload --force-render",
    )
    args = parser.parse_args()
    if args.debug:
        args.once = True
        args.no_upload = True
        args.force_render = True
    return args


if __name__ == "__main__":
    main()
