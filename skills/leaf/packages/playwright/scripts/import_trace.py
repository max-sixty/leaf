#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["click>=8", "pillow>=12.1"]
# ///
"""Index an immutable Playwright format-9 archive for Leaf's playwright-trace.

The archive remains the evidence owner. This producer reads entries in memory,
never extracts archive paths, and imports original raster bytes through the
chosen Leaf launcher's page-media command. Stdout is the complete manifest for
`leaf data set`; diagnostics use stderr. The page must already bind its source.
API parameters remain in the archive and viewer, since a manifest reaches every
page user and should not duplicate captured URLs or filled values.
Native tracing-group ancestry prefixes child action titles; groups retain their
own titles, and parents outside a stream supply no label.

Each trace stream keeps its native monotonic clock. Capture records supply page
identity; no nearest-frame heuristic associates page-less calls. Main-frame DOM
snapshots supply phase times, PNG checkpoints supply image times, and ARIA JSON
supplies separate tree times. Saved-tree paths identify nodes within that one
phase, including duplicate names, rather than promising live DOM identity or
exact correspondence between a tree box and pixels captured earlier.

Other archive versions are refused: adapting Playwright's internal format is an
explicit package change, rather than guessing at a newer or older producer.
"""

import hashlib
import io
import json
import math
import subprocess
import tempfile
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile

import click
from PIL import Image, UnidentifiedImageError


class TraceError(ValueError):
    """The archive cannot supply the review evidence this package presents."""


PHASES = {"before", "action", "after"}


def _string(value, where):
    if not isinstance(value, str) or not value:
        raise TraceError(f"{where}: expected a nonempty string")
    return value


def _number(value, where):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise TraceError(f"{where}: expected a finite number")
    return value


def _json(raw, where):
    try:
        value = json.loads(raw, parse_constant=lambda value: _number(value, where))
    except (ValueError, UnicodeDecodeError) as error:
        raise TraceError(f"{where}: invalid JSON ({error})") from error
    return value


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
                title = _string(event.get("title"), f"{child_id} tracing group title")
                if title not in inherited:
                    inherited = (*inherited, title)
            contexts[child_id] = inherited
    return contexts


class _StreamCaptures:
    """One native stream's page identities and captured call phases.

    Keeping these together prevents a later stream's namespace from changing an
    earlier stream's page or phase reading. A phase names exactly one main page.
    """

    def __init__(self, name: str, identity: str):
        self.name = name
        self.identity = identity
        self.pages = {}
        self.phases = {}

    def page_key(self, native_id):
        _string(native_id, "pageId")
        key = f"{self.identity}-page-{_digest(native_id)}"
        self.pages[key] = {"id": key, "stream": self.identity, "pageId": native_id}
        return key

    def phase(self, call_id, phase, native_page):
        _string(call_id, "capture callId")
        if phase not in PHASES:
            raise TraceError(f"unsupported capture phase {phase!r}")
        page = self.page_key(native_page)
        held = self.phases.setdefault(
            (call_id, phase),
            {"pageId": page, "timestamp": None, "imageId": None, "tree": None},
        )
        if held["pageId"] != page:
            raise TraceError(
                f"{self.name}: one call phase captured multiple main pages"
            )
        return held


def _nodes(tree, where):
    """Pointable nodes named by their paths in the original ARIA JSON tree."""
    if not isinstance(tree, list):
        raise TraceError(f"{where}: expected an accessibility node array")
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
            if not isinstance(child, dict):
                raise TraceError(f"{where}/{path}: expected a node or text")
            fields = {field: child.get(field) for field in ("role", "name", "text")}
            if any(
                value is not None and not isinstance(value, str)
                for value in fields.values()
            ):
                raise TraceError(f"{where}/{path}: role, name and text must be strings")
            box = child.get("box")
            if box is not None:
                if not isinstance(box, dict) or set(box) != {
                    "x",
                    "y",
                    "width",
                    "height",
                }:
                    raise TraceError(f"{where}/{path}: invalid node box")
                box = {
                    key: _number(value, f"{where}/{path}/box/{key}")
                    for key, value in box.items()
                }
            result.append({"path": path, **fields, "box": box})
            if "children" in child:
                if not isinstance(child["children"], list):
                    raise TraceError(f"{where}/{path}: children must be an array")
                walk(child["children"], f"{path}/children")

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
            records = [
                _json(line, "Leaf page media") for line in completed.stdout.splitlines()
            ]
            if len(records) != len(paths[start : start + 100]):
                raise TraceError("Leaf page media returned an incomplete image reading")
            for record, source in zip(records, paths[start : start + 100], strict=True):
                if not isinstance(record, dict) or record.get("source") != str(source):
                    raise TraceError(
                        "Leaf page media returned a different source image"
                    )
                urls.append(_string(record.get("path"), "Leaf page media path"))
        return urls


def import_trace(trace: Path, *, page: Path, launcher: Path, viewer_url: str) -> dict:
    """Read native stream/action/image/tree facts, then import their original rasters."""
    archive_bytes = trace.read_bytes()
    archive_hash = hashlib.sha256(archive_bytes).hexdigest()
    prefix = f"trace-{archive_hash}"
    streams, pages, actions, images, rasters = [], {}, [], [], []
    try:
        archive = ZipFile(io.BytesIO(archive_bytes))
    except BadZipFile as error:
        raise TraceError(f"{trace}: not a ZIP archive ({error})") from error
    with archive:
        names = archive.namelist()
        if len(set(names)) != len(names):
            raise TraceError("trace archive repeats an entry name")
        for name in names:
            path = PurePosixPath(name)
            if (
                path.is_absolute()
                or ".." in path.parts
                or "\\" in name
                or "\x00" in name
            ):
                raise TraceError(f"unsafe archive entry name {name!r}")
        stream_names = sorted(name for name in names if name.endswith(".trace"))
        if not stream_names:
            raise TraceError("archive contains no .trace streams")

        def read(name):
            _string(name, "archive resource path")
            if name not in names:
                raise TraceError(f"archive is missing resource {name!r}")
            return archive.read(name)

        for stream_name in stream_names:
            events = [
                _json(line, f"{stream_name}:{index + 1}")
                for index, line in enumerate(read(stream_name).splitlines())
                if line.strip()
            ]
            if not events or any(not isinstance(event, dict) for event in events):
                raise TraceError(f"{stream_name}: expected trace event objects")
            context = events[0]
            if context.get("type") != "context-options" or context.get("version") != 9:
                raise TraceError(
                    f"{stream_name}: unsupported trace format {context.get('version')!r}; this package reads format 9"
                )
            stream_id = f"{prefix}-stream-{_digest(stream_name)}"
            streams.append(
                {
                    "id": stream_id,
                    "origin": _string(context.get("origin"), f"{stream_name} origin"),
                    "playwrightVersion": _string(
                        context["playwrightVersion"], "playwrightVersion"
                    )
                    if "playwrightVersion" in context
                    else None,
                    "wallTime": _number(context["wallTime"], "wallTime")
                    if "wallTime" in context
                    else None,
                    "monotonicTime": _number(context["monotonicTime"], "monotonicTime")
                    if "monotonicTime" in context
                    else None,
                }
            )
            calls = {}
            capture = _StreamCaptures(stream_name, stream_id)

            for index, event in enumerate(events[1:], 1):
                kind = event.get("type")
                if kind == "context-options" and event.get("version") != 9:
                    raise TraceError(
                        f"{stream_name}: unsupported trace format {event.get('version')!r}; this package reads format 9"
                    )
                if kind in {"before", "action"}:
                    call_id = _string(event.get("callId"), "action callId")
                    if "parentId" in event:
                        _string(event["parentId"], f"{call_id} parentId")
                    if call_id in calls:
                        raise TraceError(f"{stream_name}: repeated action {call_id!r}")
                    calls[call_id] = dict(event)
                elif kind == "after":
                    call_id = _string(event.get("callId"), "after callId")
                    if call_id not in calls:
                        raise TraceError(
                            f"{stream_name}: completion has no action {call_id!r}"
                        )
                    if "parentId" in event:
                        _string(event["parentId"], f"{call_id} parentId")
                        if (
                            "parentId" in calls[call_id]
                            and event["parentId"] != calls[call_id]["parentId"]
                        ):
                            raise TraceError(f"{call_id}: conflicting parentId")
                    calls[call_id].update(event)
                elif kind == "event" and event.get("method") in {"page", "pageClosed"}:
                    capture.page_key(event["params"]["pageId"])
                elif kind == "frame-snapshot":
                    snapshot = event["snapshot"]
                    if snapshot.get("isMainFrame"):
                        held = capture.phase(
                            snapshot["callId"], snapshot["phase"], snapshot["pageId"]
                        )
                        held["timestamp"] = _number(
                            snapshot["timestamp"], "DOM timestamp"
                        )
                elif kind in {"screencast-frame", "screenshot"}:
                    raw = read(event["file"])
                    suffix = ".jpg" if kind == "screencast-frame" else ".png"
                    expected_format = "JPEG" if suffix == ".jpg" else "PNG"
                    try:
                        with Image.open(io.BytesIO(raw)) as image:
                            if image.format != expected_format:
                                raise TraceError(
                                    f"{event['file']}: expected {expected_format}"
                                )
                            image.verify()
                            width, height = image.size
                    except (UnidentifiedImageError, OSError, SyntaxError) as error:
                        raise TraceError(
                            f"{event['file']}: invalid image ({error})"
                        ) from error
                    image_id = f"{stream_id}-image-{index}"
                    is_checkpoint = kind == "screenshot"
                    images.append(
                        {
                            "id": image_id,
                            "pageId": capture.page_key(event["pageId"]),
                            "stream": stream_id,
                            "timestamp": _number(event["timestamp"], "image timestamp"),
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
                        if held["imageId"] is not None:
                            raise TraceError("call phase repeats a checkpoint image")
                        held["imageId"] = image_id
                        if held["timestamp"] is None:
                            held["timestamp"] = event["timestamp"]
                elif kind == "aria-snapshot":
                    held = capture.phase(
                        event["callId"], event["phase"], event["pageId"]
                    )
                    if held["tree"] is not None:
                        raise TraceError("call phase repeats an accessibility tree")
                    timestamp = _number(event["timestamp"], "tree timestamp")
                    held["tree"] = {
                        "timestamp": timestamp,
                        "nodes": _nodes(
                            _json(read(event["file"]), event["file"]), event["file"]
                        ),
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
                title = _string(title, f"{call_id} action title")
                if not (
                    event.get("class") == "Tracing"
                    and event.get("method") == "tracingGroup"
                ):
                    title = " · ".join(
                        [label for label in group_contexts[call_id] if label != title]
                        + [title]
                    )
                params = event.get("params", {})
                if not isinstance(params, dict):
                    raise TraceError(f"{call_id}: expected action params object")
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
                    error = _string(error.get("message"), f"{call_id} error message")
                elif error is not None:
                    error = _string(error, f"{call_id} error")
                actions.append(
                    {
                        "id": f"{stream_id}-call-{_digest(call_id)}",
                        "stream": stream_id,
                        "callId": call_id,
                        "pageId": action_page,
                        "title": title,
                        "startTime": _number(
                            event.get("startTime"), f"{call_id} startTime"
                        ),
                        "endTime": _number(event["endTime"], f"{call_id} endTime")
                        if "endTime" in event
                        else None,
                        "error": error,
                        "phases": phases,
                    }
                )
            unknown_calls = {call_id for call_id, _ in capture.phases} - calls.keys()
            if unknown_calls:
                raise TraceError(
                    f"{stream_name}: captures name unknown calls {sorted(unknown_calls)}"
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
    if not viewer_url.startswith(("http://", "https://")) or any(
        char.isspace() for char in viewer_url
    ):
        raise click.ClickException("viewer URL must be an HTTP(S) URL")
    try:
        value = import_trace(
            trace,
            page=page.resolve(),
            launcher=launcher.resolve(),
            viewer_url=viewer_url,
        )
    except (TraceError, KeyError, BadZipFile) as error:
        raise click.ClickException(f"import_trace: {error}") from error
    click.echo(json.dumps(value, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
