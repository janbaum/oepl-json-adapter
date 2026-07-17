# OpenEPaperLink Dashboard Renderer

Small Python service that renders dashboard images and uploads them to OpenEPaperLink tags through the AP `/imgupload` endpoint.

The first scaffold includes:

- Docker image and Compose service
- YAML config loading
- OpenEPaperLink image upload client
- Placeholder data source aggregation
- Pillow-based 7.5 inch dashboard renderer
- Change-hash check to avoid uploading identical images

## Quick Start

1. Copy the example config:

   ```sh
   cp config/config.example.yaml config/config.yaml
   ```

2. Edit `config/config.yaml` with your AP IP and tag MAC.

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

- Add real CalDAV calendar/task fetching.
- Add train departure provider.
- Add RSS feed parsing.
- Tune the renderer to the exact detected Nebular resolution.
