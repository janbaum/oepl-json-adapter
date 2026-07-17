from __future__ import annotations

from pathlib import Path

import requests


class OpenEPaperLinkClient:
    def __init__(self, base_url: str, timeout_seconds: int = 60) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def upload_image(self, mac: str, image_path: Path, *, dither: bool) -> None:
        with image_path.open("rb") as file:
            response = requests.post(
                f"{self.base_url}/imgupload",
                data={"mac": mac, "dither": "1" if dither else "0"},
                files={"file": file},
                timeout=self.timeout_seconds,
            )
        response.raise_for_status()
