#!/usr/bin/env python3
"""Print production agent timings for one Leaf event or public session reference."""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUERY_URL = (
    "https://api.cloudflare.com/client/v4/accounts/"
    "{account}/workers/observability/telemetry/query"
)
EVENT_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
SESSION_REFERENCE = re.compile(r"^[0-9]{12}$")
ACCOUNT_ID = re.compile(r'^account_id\s*=\s*"([0-9a-f]+)"$', re.MULTILINE)
SAFE_FIELDS = (
    "eventId",
    "eventIds",
    "reference",
    "route",
    "durationMs",
    "status",
    "buffered",
    "turnId",
    "error",
)


def account_id() -> str:
    """Read the public account id from the deployment configuration."""
    config = (ROOT / "worker" / "wrangler.toml").read_text(encoding="utf-8")
    match = ACCOUNT_ID.search(config)
    if match is None:
        raise RuntimeError("worker/wrangler.toml has no Cloudflare account_id")
    return match.group(1)


def query_body(key: str, value: str, now_ms: int) -> dict:
    """Build one bounded Workers Observability query."""
    filters = [
        {
            "key": "component",
            "operation": "eq",
            "type": "string",
            "value": "leaf-agent",
        }
    ]
    lookup = {}
    if key == "eventId":
        lookup["needle"] = {"value": value, "isRegex": False, "matchCase": True}
    else:
        filters.append(
            {"key": key, "operation": "eq", "type": "string", "value": value}
        )
    return {
        "queryId": "leaf-agent-diagnostic",
        "timeframe": {"from": now_ms - 24 * 60 * 60 * 1000, "to": now_ms},
        "view": "events",
        "limit": 100,
        "parameters": {
            "datasets": [],
            "filterCombination": "and",
            "filters": filters,
            **lookup,
        },
    }


def event_ids(response: dict) -> set[str]:
    """Read every canonical event id carried by matching telemetry."""
    found = set()
    for item in response.get("result", {}).get("events", {}).get("events", []):
        source = item.get("source") or {}
        if source.get("component") != "leaf-agent":
            continue
        if isinstance(source.get("eventId"), str):
            found.add(source["eventId"])
        found.update(
            event_id
            for event_id in source.get("eventIds", [])
            if isinstance(event_id, str)
        )
    return found


def safe_records(response: dict, event_id: str) -> list[dict]:
    """Keep only Leaf's declared timing fields from matching telemetry events."""
    records = []
    events = response.get("result", {}).get("events", {}).get("events", [])
    for item in events:
        source = item.get("source") or {}
        if source.get("component") != "leaf-agent":
            continue
        if source.get("eventId") != event_id and event_id not in source.get(
            "eventIds", []
        ):
            continue
        record = {
            "timestamp": item.get("timestamp"),
            "dataset": item.get("dataset"),
            "event": source.get("event"),
        }
        record.update({key: source[key] for key in SAFE_FIELDS if key in source})
        records.append(record)
    records.sort(key=lambda record: record["timestamp"])
    if records and isinstance(records[0]["timestamp"], (int, float)):
        origin = records[0]["timestamp"]
        for record in records:
            record["elapsedMs"] = round(record["timestamp"] - origin)
    return records


def query(key: str, value: str, token: str, now_ms: int) -> dict:
    """Fetch recent telemetry matching one indexed field from Cloudflare."""
    request = urllib.request.Request(
        QUERY_URL.format(account=account_id()),
        data=json.dumps(query_body(key, value, now_ms), separators=(",", ":")).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as error:
        raise RuntimeError(
            f"Cloudflare log query failed with HTTP {error.code}"
        ) from error
    if not payload.get("success"):
        raise RuntimeError("Cloudflare log query failed")
    return payload


def main(arguments: list[str]) -> int:
    """Query and print safe JSONL records."""
    if len(arguments) != 1 or EVENT_ID.fullmatch(arguments[0]) is None:
        print(
            "usage: query-site-agent-logs.py EVENT_ID|SESSION_REFERENCE",
            file=sys.stderr,
        )
        return 2
    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    if not token:
        print("CLOUDFLARE_API_TOKEN is required", file=sys.stderr)
        return 2
    lookup = arguments[0]
    now_ms = round(time.time() * 1000)
    if SESSION_REFERENCE.fullmatch(lookup):
        response = query("reference", lookup, token, now_ms)
        wanted_event_ids = event_ids(response)
    else:
        wanted_event_ids = {lookup}
    records = [
        record
        for event_id in sorted(wanted_event_ids)
        for record in safe_records(query("eventId", event_id, token, now_ms), event_id)
    ]
    records.sort(key=lambda record: record["timestamp"])
    if not records:
        print(f"no recent leaf-agent logs found for {lookup}", file=sys.stderr)
        return 1
    for record in records:
        print(json.dumps(record, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
