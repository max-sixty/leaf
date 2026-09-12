#!/usr/bin/env python3
"""Post one hosted reply to the already-running Leaf adapter."""

import json
import os
import sys
import time
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


def response_payload(arguments: list[str]) -> dict[str, str]:
    """Parse the canonical reply fields the hosted adapter accepts."""
    usage = "$LEAF_REPLY EVENT_ID TEXT [--quote TEXT] [--section ID] [--part ID]"
    if len(arguments) < 2:
        fail(f"usage: {usage}")
    event, text, *options = arguments
    payload = {"event": event, "text": text}
    while options:
        if len(options) < 2 or options[0] not in {"--quote", "--section", "--part"}:
            fail(f"usage: {usage}")
        option, value, *options = options
        key = option.removeprefix("--")
        if key in payload:
            fail(f"{option} may be supplied once")
        payload[key] = value
    return payload


def main() -> None:
    entered_at_ms = time.time_ns() // 1_000_000
    payload = response_payload(sys.argv[1:])
    route = published_route(Path.cwd())
    token_path = Path(os.environ["LEAF_REPLY_TOKEN"])
    token = token_path.read_text(encoding="utf-8")
    request_at_ms = time.time_ns() // 1_000_000
    request = urllib.request.Request(
        f"http://127.0.0.1:8080{route}/_leaf/agent/respond",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Leaf-Agent-Helper-Entered-At-Ms": str(entered_at_ms),
            "Leaf-Agent-Helper-Request-At-Ms": str(request_at_ms),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode()
    except urllib.error.HTTPError as error:
        fail(error.read().decode())
    print(body)


if __name__ == "__main__":
    main()
