#!/usr/bin/env python3
"""Print hosted agent timings for one Leaf event or public session reference."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised by the Python 3.10 gate
    import tomli as tomllib

ROOT = Path(__file__).resolve().parent.parent
QUERY_URL = (
    "https://api.cloudflare.com/client/v4/accounts/"
    "{account}/workers/observability/telemetry/query"
)
ANALYTICS_URL = (
    "https://api.cloudflare.com/client/v4/accounts/{account}/analytics_engine/sql"
)
LOG_WINDOW_BEFORE_MS = 60 * 1000
LOG_WINDOW_AFTER_MS = 19 * 60 * 1000
EVENT_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
SESSION_REFERENCE = re.compile(r"^[0-9]{12}$")
ACCOUNT_ID = re.compile(r'^account_id\s*=\s*"([0-9a-f]+)"$', re.MULTILINE)
SAFE_FIELDS = (
    "eventId",
    "eventIds",
    "reference",
    "route",
    "durationMs",
    "attempts",
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


def analytics_datasets() -> tuple[str, ...]:
    """Read every hosted event index from the deployment configuration."""
    config = tomllib.loads(
        (ROOT / "worker" / "wrangler.toml").read_text(encoding="utf-8")
    )
    environments = [config, *config.get("env", {}).values()]
    return tuple(
        dict.fromkeys(
            binding["dataset"]
            for environment in environments
            for binding in environment.get("analytics_engine_datasets", ())
        )
    )


def query_body(event_id: str, from_ms: int, to_ms: int) -> dict:
    """Build one unsampled, event-focused Workers Observability query."""
    return {
        "queryId": "leaf-agent-diagnostic",
        "timeframe": {"from": from_ms, "to": to_ms},
        "view": "events",
        "limit": 100,
        "parameters": {
            "datasets": [],
            "filterCombination": "and",
            "filters": [
                {
                    "key": "component",
                    "operation": "eq",
                    "type": "string",
                    "value": "leaf-agent",
                }
            ],
            # Full-text lookup also finds a batched turn's `eventIds` array. The
            # Analytics Engine index below keeps this query narrow enough that
            # Cloudflare does not adaptively sample those matching records.
            "needle": {
                "value": event_id,
                "isRegex": False,
                "matchCase": True,
            },
        },
    }


def analytics_statement(dataset: str, lookup: str) -> str:
    """Select accepted event ids and timestamps for one public lookup key."""
    key = "blob6" if SESSION_REFERENCE.fullmatch(lookup) else "index1"
    return (
        f"SELECT timestamp,index1 FROM {dataset} "
        f"WHERE {key}='{lookup}' AND timestamp > NOW() - INTERVAL '1' DAY "
        "ORDER BY timestamp LIMIT 100"
    )


def analytics_rows(dataset: str, lookup: str, token: str) -> list[dict]:
    """Query one configured Analytics Engine event index."""
    request = urllib.request.Request(
        ANALYTICS_URL.format(account=account_id()),
        data=analytics_statement(dataset, lookup).encode(),
        headers={"Authorization": f"Bearer {token}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as error:
        raise RuntimeError(
            f"Cloudflare event index query for {dataset} failed with HTTP {error.code}"
        ) from error
    return payload.get("data", [])


def indexed_events(lookup: str, token: str) -> dict[str, int]:
    """Read each matching event's first accepted timestamp from every environment."""
    events = {}
    for dataset in analytics_datasets():
        for row in analytics_rows(dataset, lookup, token):
            event_id = row.get("index1")
            timestamp = row.get("timestamp")
            if not isinstance(event_id, str) or not isinstance(timestamp, str):
                continue
            accepted_ms = round(
                datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                .replace(tzinfo=timezone.utc)
                .timestamp()
                * 1000
            )
            events.setdefault(event_id, accepted_ms)
    return events


def safe_records(responses: list[dict], wanted_event_ids: set[str]) -> list[dict]:
    """Deduplicate telemetry and keep Leaf's declared timing fields."""
    records = []
    seen = set()
    for item in (
        item
        for response in responses
        for item in response.get("result", {}).get("events", {}).get("events", [])
    ):
        fingerprint = json.dumps(item, sort_keys=True, separators=(",", ":"))
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        source = item.get("source") or {}
        if source.get("component") != "leaf-agent":
            continue
        carried_event_ids = {
            event_id
            for event_id in source.get("eventIds", [])
            if isinstance(event_id, str)
        }
        if isinstance(source.get("eventId"), str):
            carried_event_ids.add(source["eventId"])
        if carried_event_ids.isdisjoint(wanted_event_ids):
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


def query(event_id: str, accepted_ms: int, token: str) -> dict:
    """Fetch the unsampled telemetry window around one accepted event."""
    request = urllib.request.Request(
        QUERY_URL.format(account=account_id()),
        data=json.dumps(
            query_body(
                event_id,
                accepted_ms - LOG_WINDOW_BEFORE_MS,
                accepted_ms + LOG_WINDOW_AFTER_MS,
            ),
            separators=(",", ":"),
        ).encode(),
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
    abr_level = payload.get("result", {}).get("statistics", {}).get("abr_level", 1)
    if abr_level not in (None, 1):
        raise RuntimeError(f"Cloudflare log query was sampled at ABR level {abr_level}")
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
    events = indexed_events(lookup, token)
    wanted_event_ids = set(events)
    responses = [
        query(event_id, accepted_ms, token)
        for event_id, accepted_ms in sorted(events.items())
    ]
    records = safe_records(responses, wanted_event_ids)
    if not records:
        print(f"no recent leaf-agent logs found for {lookup}", file=sys.stderr)
        return 1
    for record in records:
        print(json.dumps(record, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
