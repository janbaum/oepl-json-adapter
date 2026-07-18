# OpenEPaperLink Dashboard Renderer

Small Python service that renders dashboard images and uploads them to OpenEPaperLink tags through the AP `/imgupload` endpoint.

The first scaffold includes:

- Docker image and Compose service
- YAML config loading
- OpenEPaperLink image upload client
- CalDAV calendar/task fetching for Nextcloud and other CalDAV servers
- RSS/Atom feed fetching
- Train departure fetching through RMV HAPI
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

## Efficiency

By default, the service uploads only when dashboard content changes:

```yaml
efficiency:
  upload_only_on_content_change: true
```

The content hash is based on calendar events, tasks, departures, and news. Render-only values such as the clock and tag battery status are intentionally ignored, so they do not wake tags by themselves.

Battery status is read from the AP tag database endpoint and rendered in the header when enabled:

```yaml
dashboards:
  overview:
    rendering:
      show_battery: true
```

OpenEPaperLink LUT behavior can be set per tag:

```yaml
tags:
  - name: hallway
    lut: ""
```

Leave `lut` empty unless you have confirmed a mode that works well with your exact tag type. Common UI/API modes include `default`, `no-repeat`, `fast-no-reds`, and `fast`.

OpenEPaperLink also has lower-level diff image and LUT concepts, but for this container's `/imgupload` workflow the reliable battery saver is avoiding uploads entirely when content is unchanged. For display refresh behavior, configure the tag's LUT in the OpenEPaperLink tag settings or the per-tag `lut` field above.

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
- Set `sources.transit.enabled: true` and add RMV HAPI station IDs.
- Tune the renderer to the exact detected Nebular resolution.

## RMV Transit

Create an RMV HAPI access ID and put it in `.env`:

```env
RMV_ACCESS_ID=your-rmv-hapi-access-id
```

Show all departures from one station:

```yaml
sources:
  transit:
    enabled: true
    provider: "rmv_hapi"
    mode: "departure_board"
    src_station_id: "3000010"
    all_departures: true
    excluded_products: ["ICE", "IC", "EC"]
```

Show departures from one station only toward another station/direction:

```yaml
sources:
  transit:
    enabled: true
    provider: "rmv_hapi"
    mode: "departure_board"
    src_station_id: "3004801"
    direction: "3000010"
    all_departures: false
    included_products: ["S", "RB", "RE"]
```

Show route options from source to destination:

```yaml
sources:
  transit:
    enabled: true
    provider: "rmv_hapi"
    mode: "trip"
    src_station_id: "3004801"
    dst_station_id: "3000010"
    excluded_products: ["ICE", "IC", "EC"]
```

For a dedicated grouped transport dashboard, point a tag at the `transportation` dashboard and configure multiple directions:

```yaml
tags:
  - name: transport
    dashboard: "transportation"

dashboards:
  transportation:
    title: "Transit"
    layout: "transportation"
    sections:
      transit:
        max_items: 12
        directions:
          - name: "FfM Hbf -> Darmstadt Hbf"
            mode: "trip"
            src_station_id: "..."
            src_label: "FfM Hbf"
            dst_station_id: "..."
            dst_label: "Darmstadt Hbf"
            max_items: 2
            excluded_products: ["ICE", "IC", "EC"]
          - name: "FfM Hbf -> Offenbach Marktplatz"
            mode: "trip"
            src_station_id: "..."
            src_label: "FfM Hbf"
            dst_station_id: "..."
            dst_label: "Offenbach Marktplatz"
            max_items: 2
          - name: "Willy-Brandt-Platz -> Suedbahnhof"
            mode: "trip"
            src_station_id: "..."
            src_label: "FfM Willy-Brandt-Platz"
            dst_station_id: "..."
            dst_label: "FfM Suedbahnhof"
            max_items: 2

sources:
  transit:
    enabled: true
    provider: "rmv_hapi"
    access_id: "${RMV_ACCESS_ID}"
```

The renderer keeps the configured order, so put directions from the same source station next to each other. Directions can also live under `sources.transit.directions` if you want one global transport setup, but dashboard-local directions are clearer once you have multiple dashboards.

For a compact transport-only config, this alias is also supported:

```yaml
dashboards:
  oeffis:
    title: "Oeffis"
    sections:
      directions:
        enabled: true
        max_items: 10

sources:
  transit:
    enabled: false
    provider: "rmv_hapi"
    access_id: "${RMV_ACCESS_ID}"

  directions:
    - name: "FfM Sued -> Darmstadt Hbf"
      mode: "trip"
      src_station_id: "3000912"
      dst_station_id: "3004734"
      max_items: 2
```

Use RMV's `location.name` endpoint to look up station IDs:

```text
https://www.rmv.de/hapi/location.name?input=Frankfurt%20Hauptbahnhof&format=json&accessId=...
```
