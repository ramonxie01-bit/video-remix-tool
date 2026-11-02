"""Download flet-windows.zip for the installed flet-desktop version.

The archive is stored at packaging/.flet_client/flet-windows.zip (not committed).
packaging/remix.spec copies it to flet_desktop/app/ inside the frozen app so
first launch extracts the desktop client with no network and no pip.
"""
from __future__ import annotations

import shutil
import urllib.request

from flet_desktop_bundle import (
    CLIENT_ZIP,
    assert_windows_client_zip,
    installed_flet_desktop_version,
    windows_client_url,
)


def download(url: str, dest) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "video-remix-tool-packaging"})
    print(f"Downloading {url}")
    with urllib.request.urlopen(req, timeout=180) as resp, tmp.open("wb") as out:
        shutil.copyfileobj(resp, out)
    tmp.replace(dest)


def main() -> None:
    version = installed_flet_desktop_version()
    url = windows_client_url(version)
    if CLIENT_ZIP.is_file():
        try:
            assert_windows_client_zip(CLIENT_ZIP)
        except SystemExit:
            print(f"Replacing invalid {CLIENT_ZIP}")
        else:
            print(f"Using existing {CLIENT_ZIP} for flet-desktop {version}")
            return
    download(url, CLIENT_ZIP)
    assert_windows_client_zip(CLIENT_ZIP)
    print(f"OK {CLIENT_ZIP} ({CLIENT_ZIP.stat().st_size} bytes) flet-desktop {version}")


if __name__ == "__main__":
    main()
