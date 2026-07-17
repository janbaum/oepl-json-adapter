# OpenEPaperLink Dashboard Renderer

Small Python service that renders dashboard images and uploads them to OpenEPaperLink tags through the AP `/imgupload` endpoint.

The first scaffold includes:

- Docker image and Compose service
- YAML config loading
- OpenEPaperLink image upload client
- CalDAV calendar/task fetching for Nextcloud and other CalDAV servers
- RSS/Atom feed fetching
- Train departure fetching through `v6.db.transport.rest`
- Placeholder data fallback
- Pillow-based 7.5 inch dashboard renderer
- Change-hash check to avoid uploading identical images

## Quick Start

1. Edit `config/config.yaml` with your AP IP and tag MAC.

2. Export credentials if you enable CalDAV:

   ```sh
   export NEXTCLOUD_USERNAME="your-user"
   export NEXTCLOUD_APP_PASSWORD="your-app-password"
   ```

   You can also copy `.env.example` to `.env`; Docker Compose will read it automatically.

3. Build and run:

   ```sh
   docker compose up --build
   ```

Generated images and upload state are stored in `./data`.

## Project Layout

```text
config/                  Example and local configuration
data/                    Runtime output/cache directory
src/epaper_dashboard/    Python package
  sources/               Calendar, task, transit, and RSS source adapters
  config.py              YAML/env config loading
  models.py              Shared data models
  render.py              Pillow dashboard rendering
  upload.py              OpenEPaperLink /imgupload client
  main.py                Scheduler loop and orchestration
```

## Next Steps

- Set `sources.caldav.enabled: true` after adding valid Nextcloud credentials.
- Leave `discover: true` for the first run; use `calendar_urls` and `task_urls` later if you want explicit collection selection.
- Set `sources.rss.enabled: true` and add feed URLs for news.
- Set `sources.transit.enabled: true` and add a `station_id` from `https://v6.db.transport.rest/locations?query=...`.
- Tune the renderer to the exact detected Nebular resolution.
