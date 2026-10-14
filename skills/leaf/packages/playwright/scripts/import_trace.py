#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["click>=8.2", "pillow>=12.1"]
# ///
"""Index an immutable Playwright format-9 archive for Leaf's playwright-trace.

The archive remains the evidence owner. This producer reads entries in memory,
never extracts archive paths, and imports original raster bytes through the
chosen Leaf launcher's page-media command. Stdout is the complete manifest for
`leaf data set`; diagnostics use stderr. The page must already bind its source.
Native methods and input events retain selector, key, pointer coordinates and the
input snapshot's viewport for interaction review. Other API parameters remain in the archive and viewer, since
a manifest reaches every page user and should not duplicate URLs or filled values.
Input events have no native timestamp: action-phase times describe their captured
snapshot, not a simultaneous measurement of pointer coordinates and image pixels.
Native tracing-group ancestry prefixes child action titles; groups retain their
own titles, and parents outside a stream supply no label.

Each trace stream keeps its native monotonic clock. Capture records supply page
identity; no nearest-frame heuristic associates page-less calls. Main-frame DOM
snapshots supply phase times, PNG checkpoints supply image times, and ARIA JSON
supplies separate tree times. Saved-tree paths identify nodes within that one
phase, including duplicate names, rather than promising live DOM identity or
exact correspondence between a tree box and pixels captured earlier.

Other archive versions are refused: adapting Playwright's internal format is an
explicit package change, rather than guessing at a newer or older producer. Within
format 9 the archive is read as Playwright writes it, and a damaged one is not
diagnosed here.
"""

import hashlib
import io
import json
import subprocess
import tempfile
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import click
from PIL import Image


class TraceError(ValueError):
    """The archive cannot supply the review evidence this package presents."""


def _digest(value):
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def _group_contexts(calls, stream_name):
    """Resolve native parent edges, refusing cycles without inferring missing parents."""
    contexts = {}
    for call_id in calls:
        chain, seen = [], set()
        current = call_id
        while current in calls and current not in contexts:
            if current in seen:
                raise TraceError(f"{stream_name}: action parentId cycle at {current!r}")
            seen.add(current)
            chain.append(current)
            current = calls[current].get("parentId")
        inherited = contexts.get(current, ())
        for child_id in reversed(chain):
            event = calls[child_id]
            if (
                event.get("class") == "Tracing"
                and event.get("method") == "tracingGroup"
            ):
                title = event["title"]
                if title not in inherited:
                    inherited = (*inherited, title)
            contexts[child_id] = inherited
    return contexts


def _input(event, native_input, phases, viewport):
    """Retain native input facts, without inferring gestures from display titles."""
    if native_input is None:
        # Complete action records can carry the input point/snapshot directly.
        # Format-9 action-phase snapshots also establish native input capture.
        if (
            event.get("point") is None
            and event.get("inputSnapshot") is None
            and "action" not in phases
        ):
            return None
        native_input = event
    params = event.get("params", {})
    return {field: params.get(field) for field in ("selector", "key")} | {
        "point": native_input.get("point"),
        "viewport": viewport,
    }


class _StreamCaptures:
    """One native stream's page identities and captured call phases.

    Keeping these together prevents a later stream's namespace from changing an
    earlier stream's page or phase reading.
    """

    def __init__(self, identity: str):
        self.identity = identity
        self.pages = {}
        self.phases = {}
        self.input_viewports = {}

    def page_key(self, native_id):
        key = f"{self.identity}-page-{_digest(native_id)}"
        self.pages[key] = {"id": key, "stream": self.identity, "pageId": native_id}
        return key

    def phase(self, call_id, phase, native_page):
        return self.phases.setdefault(
            (call_id, phase),
            {
                "pageId": self.page_key(native_page),
                "timestamp": None,
                "imageId": None,
                "tree": None,
            },
        )


def _nodes(tree):
    """Pointable nodes named by their paths in the original ARIA JSON tree."""
    result = []

    def walk(children, prefix):
        for index, child in enumerate(children):
            path = f"{prefix}/{index}" if prefix else str(index)
            if isinstance(child, str):
                result.append(
                    {
                        "path": path,
                        "role": None,
                        "name": None,
                        "text": child,
                        "box": None,
                    }
                )
                continue
            result.append(
                {
                    "path": path,
                    **{field: child.get(field) for field in ("role", "name", "text")},
                    "box": child.get("box"),
                }
            )
            walk(child.get("children", []), f"{path}/children")

    walk(tree, "")
    return result


def _media(page, launcher, images):
    """Hand raster bytes to Leaf's canonical writer, preserving their original bytes."""
    with tempfile.TemporaryDirectory(prefix="leaf-playwright-images-") as scratch:
        paths = []
        for index, (raw, suffix) in enumerate(images):
            path = Path(scratch) / f"{index}{suffix}"
            path.write_bytes(raw)
            paths.append(path)
        urls = []
        # A trace may hold many images; bounded batches keep command arguments small.
        for start in range(0, len(paths), 100):
            completed = subprocess.run(
                [
                    str(launcher),
                    "page",
                    "media",
                    str(page),
                    *map(str, paths[start : start + 100]),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if completed.returncode:
                raise TraceError(
                    f"Leaf page media failed: {completed.stderr.strip() or completed.stdout.strip()}"
                )
            urls += [json.loads(line)["path"] for line in completed.stdout.splitlines()]
        return urls


def import_trace(trace: Path, *, page: Path, launcher: Path, viewer_url: str) -> dict:
    """Read native stream/action/image/tree facts, then import their original rasters."""
    archive_bytes = trace.read_bytes()
    archive_hash = hashlib.sha256(archive_bytes).hexdigest()
    prefix = f"trace-{archive_hash}"
    streams, pages, actions, images, rasters = [], {}, [], [], []
    with ZipFile(io.BytesIO(archive_bytes)) as archive:
        read = archive.read
        stream_names = sorted(
            name for name in archive.namelist() if name.endswith(".trace")
        )
        for stream_name in stream_names:
            events = [
                json.loads(line)
                for line in read(stream_name).splitlines()
                if line.strip()
            ]
            context = events[0]
            if context.get("type") != "context-options" or context.get("version") != 9:
                raise TraceError(
                    f"{stream_name}: unsupported trace format {context.get('version')!r}; this package reads format 9"
                )
            stream_id = f"{prefix}-stream-{_digest(stream_name)}"
            streams.append(
                {
                    "id": stream_id,
                    "origin": context["origin"],
                    **{
                        field: context.get(field)
                        for field in ("playwrightVersion", "wallTime", "monotonicTime")
                    },
                }
            )
            calls, inputs = {}, {}
            capture = _StreamCaptures(stream_id)

            for index, event in enumerate(events[1:], 1):
                kind = event.get("type")
                if kind in {"before", "action"}:
                    calls[event["callId"]] = dict(event)
                elif kind == "input":
                    inputs[event["callId"]] = event
                elif kind == "after":
                    calls[event["callId"]].update(event)
                elif kind == "event" and event.get("method") in {"page", "pageClosed"}:
                    capture.page_key(event["params"]["pageId"])
                elif kind == "frame-snapshot":
                    snapshot = event["snapshot"]
                    if snapshot.get("isMainFrame"):
                        held = capture.phase(
                            snapshot["callId"], snapshot["phase"], snapshot["pageId"]
                        )
                        held["timestamp"] = snapshot["timestamp"]
                        if snapshot["phase"] == "action" and "viewport" in snapshot:
                            capture.input_viewports[snapshot["callId"]] = snapshot[
                                "viewport"
                            ]
                elif kind in {"screencast-frame", "screenshot"}:
                    raw = read(event["file"])
                    suffix = ".jpg" if kind == "screencast-frame" else ".png"
                    with Image.open(io.BytesIO(raw)) as image:
                        width, height = image.size
                    image_id = f"{stream_id}-image-{index}"
                    is_checkpoint = kind == "screenshot"
                    images.append(
                        {
                            "id": image_id,
                            "pageId": capture.page_key(event["pageId"]),
                            "stream": stream_id,
                            "timestamp": event["timestamp"],
                            "kind": "checkpoint" if is_checkpoint else "frame",
                            "url": "",
                            "width": width,
                            "height": height,
                            "callId": event["callId"] if is_checkpoint else None,
                            "phase": event["phase"] if is_checkpoint else None,
                        }
                    )
                    rasters.append((raw, suffix))
                    if is_checkpoint:
                        held = capture.phase(
                            event["callId"], event["phase"], event["pageId"]
                        )
                        held["imageId"] = image_id
                        if held["timestamp"] is None:
                            held["timestamp"] = event["timestamp"]
                elif kind == "aria-snapshot":
                    held = capture.phase(
                        event["callId"], event["phase"], event["pageId"]
                    )
                    timestamp = event["timestamp"]
                    held["tree"] = {
                        "timestamp": timestamp,
                        "nodes": _nodes(json.loads(read(event["file"]))),
                    }
                    if held["timestamp"] is None:
                        held["timestamp"] = timestamp

            group_contexts = _group_contexts(calls, stream_name)
            for call_id, event in calls.items():
                phases = {
                    phase: held
                    for (captured_call, phase), held in capture.phases.items()
                    if captured_call == call_id
                }
                captured_pages = {held["pageId"] for held in phases.values()}
                native_page = event.get("pageId")
                action_page = (
                    capture.page_key(native_page)
                    if native_page
                    else next(iter(captured_pages))
                    if len(captured_pages) == 1
                    else None
                )
                title = (
                    event.get("title")
                    or event.get("apiName")
                    or f"{event.get('class', 'API')}.{event.get('method', 'call')}"
                )
                if not (
                    event.get("class") == "Tracing"
                    and event.get("method") == "tracingGroup"
                ):
                    title = " · ".join(
                        [label for label in group_contexts[call_id] if label != title]
                        + [title]
                    )
                params = event.get("params", {})
                detail = next(
                    (
                        params[field]
                        for field in ("key",)
                        if isinstance(params.get(field), str)
                    ),
                    None,
                )
                if detail:
                    title = f"{title} · {detail}"
                error = event.get("error")
                if isinstance(error, dict):
                    error = error["message"]
                actions.append(
                    {
                        "id": f"{stream_id}-call-{_digest(call_id)}",
                        "stream": stream_id,
                        "callId": call_id,
                        "pageId": action_page,
                        "method": event["method"],
                        "input": _input(
                            event,
                            inputs.get(call_id),
                            phases,
                            capture.input_viewports.get(call_id),
                        ),
                        "title": title,
                        "startTime": event["startTime"],
                        "endTime": event.get("endTime"),
                        "error": error,
                        "phases": phases,
                    }
                )
            pages.update(capture.pages)

    urls = _media(page, launcher, rasters)
    for image, url in zip(images, urls, strict=True):
        image["url"] = url
    return {
        "archive": {"sha256": archive_hash, "format": 9},
        "viewerUrl": viewer_url,
        "streams": streams,
        "pages": list(pages.values()),
        "actions": actions,
        "images": images,
    }


@click.command()
@click.argument("trace", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--page",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option(
    "--leaf",
    "launcher",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--viewer-url",
    required=True,
    help="Running Playwright viewer for this same unchanged archive.",
)
def main(trace, page, launcher, viewer_url):
    """Import native TRACE rasters into PAGE and write review JSON on stdout."""
    try:
        value = import_trace(
            trace,
            page=page.resolve(),
            launcher=launcher.resolve(),
            viewer_url=viewer_url,
        )
    except (TraceError, KeyError, BadZipFile, json.JSONDecodeError) as error:
        raise click.ClickException(f"import_trace: {error}") from error
    click.echo(json.dumps(value, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
