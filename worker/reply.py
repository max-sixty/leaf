#!/usr/bin/env python3
"""Post one hosted reply to the already-running Leaf adapter."""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def fail(message: str) -> None:
    raise SystemExit(message)


def published_route(page_dir: Path) -> str:
    """Resolve a served page directory through the site's routing authority."""
    page_dir = page_dir.resolve()
    site_root = page_dir
    while not (site_root / "_leaf" / "site.json").is_file():
        if site_root.parent == site_root:
            fail("$LEAF_REPLY must run inside a published Leaf site")
        site_root = site_root.parent
    manifest = json.loads(
        (site_root / "_leaf" / "site.json").read_text(encoding="utf-8")
    )
    directory = page_dir.relative_to(site_root).as_posix()
    routes = [
        root
        for root, page in manifest["pages"].items()
        if page.get("directory") == directory
    ]
    if len(routes) != 1:
        fail("$LEAF_REPLY could not identify this page's public route")
    return "" if routes[0] == "/" else routes[0]


def main() -> None:
    if len(sys.argv) != 3:
        fail("usage: $LEAF_REPLY EVENT_ID TEXT")
    event, text = sys.argv[1:]
    route = published_route(Path.cwd())
    token_path = Path(os.environ["LEAF_REPLY_TOKEN"])
    token = token_path.read_text(encoding="utf-8")
    request = urllib.request.Request(
        f"http://127.0.0.1:8080{route}/_leaf/agent/respond",
        data=json.dumps({"event": event, "text": text}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            print(response.read().decode())
    except urllib.error.HTTPError as error:
        fail(error.read().decode())


if __name__ == "__main__":
    main()
