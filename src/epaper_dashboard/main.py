from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path

from epaper_dashboard.config import AppConfig, TagConfig, load_config
from epaper_dashboard.render import render_dashboard
from epaper_dashboard.sources.placeholder import load_placeholder_data
from epaper_dashboard.upload import OpenEPaperLinkClient

LOG = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = load_config()
    config.data_dir.mkdir(parents=True, exist_ok=True)
    client = OpenEPaperLinkClient(config.ap_base_url)

    LOG.info("Starting epaper dashboard renderer for %d tag(s)", len(config.tags))

    while True:
        started = time.monotonic()
        for tag in config.tags:
            try:
                _process_tag(config, client, tag)
            except Exception:
                LOG.exception("Failed to update tag %s", tag.name)

        sleep_for = _next_sleep(config, started)
        LOG.info("Sleeping for %s seconds", sleep_for)
        time.sleep(sleep_for)


def _process_tag(config: AppConfig, client: OpenEPaperLinkClient, tag: TagConfig) -> None:
    dashboard = config.dashboards.get(tag.dashboard, {})
    title = str(dashboard.get("title", tag.name))
    data = load_placeholder_data()

    image_path = config.data_dir / f"{tag.name}.jpg"
    render_dashboard(tag, title, data, image_path)

    digest = _sha256(image_path)
    state_path = config.data_dir / f"{tag.name}.sha256"
    previous_digest = state_path.read_text(encoding="utf-8").strip() if state_path.exists() else ""

    if digest == previous_digest:
        LOG.info("Skipping %s; rendered image unchanged", tag.name)
        return

    LOG.info("Uploading %s to %s", image_path, tag.name)
    client.upload_image(tag.mac, image_path, dither=tag.dither)
    state_path.write_text(digest, encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _next_sleep(config: AppConfig, started: float) -> int:
    interval = min(tag.refresh_seconds for tag in config.tags)
    elapsed = int(time.monotonic() - started)
    return max(30, interval - elapsed)


if __name__ == "__main__":
    main()
