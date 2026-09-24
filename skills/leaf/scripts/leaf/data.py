"""Page-bound external data: one plain JSON file per source.

`data.json` records the contract each source id was first bound to, which it keeps
for the page's lifetime; `data/<source>.json` holds that source's current value as
ordinary JSON. `leaf data set` and `data capture` validate before they write, but any
process may replace a value file, so every reading validates the value against its
contract and reports a failing one as that source's `error` rather than its value.

A source's revision is a digest of its file's bytes and `updated` its modification
time. Nothing retains an earlier value: a reader or anchor naming a revision the
source no longer holds is reading a replaced value. A document that must keep one
value binds a source id nothing rewrites.
"""

import codecs
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

import click
from unidiff import PatchedFile, PatchSet, UnidiffParseError

from .data_contracts import DataError, payload_error, working_data_bindings
from .files import json_bytes, replace_files
from .registry.storage import read_page_registry
from .schema import DATA_CONTRACT_NAME, DATA_DIR, DATA_FILE, DATA_SOURCE_NAME
from .service import PageTransaction

# From here to `unified_diff_manifest`, whose docstring states the division: unidiff
# reads the hunks, and everything here owns the manifest built around them.
_GIT_QUOTED_PATH = re.compile(
    r'(?:[^\\]|\\(?:[abtnvfr"\\]|[0-3][0-7]{2}|[0-7]{1,2}(?![0-7])))*'
)


def _decode_git_path(path: str) -> str:
    """Decode the C-style quoting Git uses for diff path fields.

    unidiff hands a quoted path back as Git wrote it, so the manifest decodes it
    here and refuses an escape Git would not have written."""
    if not path.startswith('"'):
        return path
    if len(path) < 2 or not path.endswith('"'):
        raise DataError(f"invalid quoted Git path {path!r}")
    inner = path[1:-1]
    if _GIT_QUOTED_PATH.fullmatch(inner) is None:
        raise DataError(f"invalid quoted Git path {path!r}")
    encoded = codecs.escape_decode(inner.encode("utf-8"))[0]
    if 0 in encoded:
        raise DataError("quoted Git path contains a NUL byte")
    try:
        return encoded.decode("utf-8")
    except UnicodeDecodeError as error:
        raise DataError(f"quoted Git path is not UTF-8: {path!r}") from error


def _diff_header_path(side: str, path: str) -> str:
    """One bare path written the way its `diff --git` side names it."""
    return (
        f'"{side}/{path[1:]}'
        if path.startswith('"') and path.endswith('"')
        else f"{side}/{path}"
    )


def _marked_bare_path(token: str, side: str) -> str:
    """One ---/+++ path token with its side marker removed, still quoted where Git
    quoted it.

    Git writes the marker itself, so the leading two characters are never part of
    the path, and stripping them before decoding keeps the quoting that the
    `diff --git` header is compared against. A capture made with `--no-prefix` or a
    mnemonic prefix is refused here: the widget reads the default markers."""
    marker = f"{side}/"
    if token.startswith('"') and token.endswith('"'):
        if token[1:3] == marker:
            return f'"{token[3:]}'
    elif token.startswith(marker):
        return token[2:]
    raise DataError(f"unified diff path {token!r} has no {marker} side marker")


def _diff_marked_paths(section: str) -> tuple[str | None, str | None]:
    """Read the adjacent ---/+++ file headers before the first textual hunk."""
    lines = section.split("\n")
    first_hunk = next(
        (index for index, line in enumerate(lines) if line.startswith("@@")),
        len(lines),
    )
    marked = lines[1:first_hunk]
    old = [
        (index, line[4:])
        for index, line in enumerate(marked)
        if line.startswith("--- ")
    ]
    new = [
        (index, line[4:])
        for index, line in enumerate(marked)
        if line.startswith("+++ ")
    ]
    if not old and not new:
        return None, None
    if len(old) != 1 or len(new) != 1 or new[0][0] != old[0][0] + 1:
        raise DataError("unified diff needs one adjacent ---/+++ file-header pair")
    # A traditional unified header may append a timestamp after a tab. Git's quoted
    # paths keep whitespace inside the quotes and need no special casing here.
    return old[0][1].split("\t", 1)[0], new[0][1].split("\t", 1)[0]


def _diff_rename_paths(section: str) -> tuple[str | None, str | None]:
    previous = re.search(r"^rename from (.+)$", section, re.MULTILINE)
    renamed = re.search(r"^rename to (.+)$", section, re.MULTILINE)
    if bool(previous) != bool(renamed):
        raise DataError("unified diff has an incomplete rename block")
    return (
        _decode_git_path(previous.group(1)) if previous is not None else None,
        _decode_git_path(renamed.group(1)) if renamed is not None else None,
    )


def _path_only_rename(section: str) -> tuple[str, str] | None:
    lines = section.rstrip("\n").split("\n")
    if len(lines) != 4 or lines[1] != "similarity index 100%":
        return None
    previous = re.fullmatch(r"rename from (.+)", lines[2])
    renamed = re.fullmatch(r"rename to (.+)", lines[3])
    if previous is None or renamed is None:
        return None
    old_path = previous.group(1)
    new_path = renamed.group(1)
    if old_path == '""' or new_path == '""':
        return None
    if lines[0] != (
        f"diff --git {_diff_header_path('a', old_path)} "
        f"{_diff_header_path('b', new_path)}"
    ):
        return None
    return _decode_git_path(old_path), _decode_git_path(new_path)


def _parsed_hunks(section: str, path: str) -> PatchedFile:
    """unidiff's reading of one section's textual hunks.

    unidiff ends a hunk as soon as its @@ header's declared counts are met, and
    hands any line after that back to the file parser, which absorbs it as patch
    metadata. So the reading counts as evidence only once the hunks account for
    every line from the first @@ header on."""
    # One view of where the section ends, for the parse and the count below: the
    # blank lines a patch may carry between files are neither hunk nor metadata.
    body_text = section.rstrip("\n") + "\n"
    try:
        parsed = PatchSet.from_string(body_text)
    except UnidiffParseError as error:
        # unidiff ends a refusal that quotes a line with that line's own newline.
        detail = str(error).strip()
        raise DataError(f"unsupported hunks for {path}: {detail}") from error
    if len(parsed) != 1:
        raise DataError(f"unified diff repeats a file header inside {path}")
    patched = parsed[0]
    if not patched:
        raise DataError(
            f"unsupported hunkless diff for {path}; only exact path-only renames "
            "may omit textual @@ hunks"
        )
    lines = body_text.rstrip("\n").split("\n")
    first_hunk = next(
        index for index, line in enumerate(lines) if line.startswith("@@")
    )
    body = lines[first_hunk:]
    if len(body) != len(patched) + sum(len(hunk) for hunk in patched):
        raise DataError(
            f"hunk line counts for {path} do not match the lines under them"
        )
    # unidiff reads a bare empty line as an empty context line, for a patch that
    # crossed a transport which strips trailing whitespace. `lf-diff` refuses one,
    # so capture refuses it too rather than storing evidence the page cannot draw.
    if not all(body):
        raise DataError(f"unsupported hunks for {path}: an empty line has no marker")
    return patched


def _manifest_file(section: str) -> dict:
    """One manifest entry for one `diff --git` section of the captured patch."""
    if re.search(r"^copy (?:from|to) ", section, re.MULTILINE):
        raise DataError(
            "unsupported copy diff; omit copy metadata and provide textual @@ "
            "hunks for an edited destination"
        )
    pure_rename = _path_only_rename(section)
    if pure_rename is not None:
        previous, path = pure_rename
        return {
            "key": path,
            "path": path,
            "previousPath": previous,
            "kind": "rename",
            "additions": 0,
            "deletions": 0,
            "patch": section,
        }

    header = section.split("\n", 1)[0]
    previous, renamed = _diff_rename_paths(section)
    marked_old, marked_new = _diff_marked_paths(section)
    if marked_old is None or marked_new is None:
        if re.search(r"^@@", section, re.MULTILINE):
            raise DataError(
                "unified diff has no ---/+++ file-header pair before its first hunk"
            )
        if previous is not None or renamed is not None:
            raise DataError(
                "unsupported hunkless rename; only the exact four-line "
                "path-only form may omit textual @@ hunks"
            )
        raise DataError(f"unsupported hunkless diff: {header}")

    # Git leaves ordinary spaces unquoted in `diff --git` and terminates the
    # unambiguous ---/+++ paths with a tab instead, so the header is compared with
    # the pair rebuilt from those paths rather than split at a guessed space. An
    # added or deleted file names /dev/null on one side and the surviving path on
    # both sides of the header.
    old_path = None if marked_old == "/dev/null" else _marked_bare_path(marked_old, "a")
    new_path = None if marked_new == "/dev/null" else _marked_bare_path(marked_new, "b")
    if old_path is None and new_path is None:
        raise DataError("diff file has no old or new path")
    old_path = old_path or new_path
    new_path = new_path or old_path
    if header != (
        f"diff --git {_diff_header_path('a', old_path)} "
        f"{_diff_header_path('b', new_path)}"
    ):
        raise DataError(
            "unified diff ---/+++ paths disagree with its diff --git header"
        )
    if (previous is not None and previous != _decode_git_path(old_path)) or (
        renamed is not None and renamed != _decode_git_path(new_path)
    ):
        raise DataError("unified diff rename paths disagree with its diff --git header")

    path = renamed or _decode_git_path(new_path)
    patched = _parsed_hunks(section, path)
    return {
        "key": path,
        "path": path,
        **({"previousPath": previous} if previous is not None else {}),
        "kind": "patch",
        "additions": patched.added,
        "deletions": patched.removed,
        "patch": section,
    }


def unified_diff_manifest(source: str) -> dict:
    """One captured Git patch as Leaf's fragmented manifest.

    Leaf owns the manifest and unidiff owns the hunks inside it. Each entry
    carries the file's key and paths, its change counts, and the verbatim section
    of the captured text that `lf-diff` renders once its disclosure opens — which
    is why the source is split here rather than rebuilt from unidiff's reading.

    Capture refuses what the widget cannot present as review evidence. Two of
    those refusals are Leaf's alone: copy metadata, which unidiff reads as a
    rename, and a hunkless entry that is not the exact four-line path-only
    rename, which it reports as a file with no hunks."""
    sections = [
        section
        for section in re.split(r"(?=^diff --git )", source, flags=re.MULTILINE)
        if section.startswith("diff --git ")
    ]
    if not sections:
        raise DataError("unified diff contains no files")

    files = []
    paths = set()
    for section in sections:
        entry = _manifest_file(section)
        if entry["path"] in paths:
            raise DataError(f"unified diff repeats file path {entry['path']!r}")
        paths.add(entry["path"])
        files.append(entry)
    return {"files": files}


class StaleDataError(DataError):
    """A fragment request named a source revision the source no longer holds."""


def source_file(page_dir: Path, source: str) -> Path:
    return page_dir / DATA_DIR / f"{source}.json"


def read_contracts(page_dir: Path) -> dict[str, str]:
    """Source id → the contract `data.json` records for it."""
    path = page_dir / DATA_FILE
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (UnicodeDecodeError, ValueError) as error:
        raise DataError(f"{path}: invalid JSON ({error})") from error
    sources = stored.get("sources") if isinstance(stored, dict) else None
    if not isinstance(sources, dict) or set(stored) != {"sources"}:
        raise DataError(f"{path}: data must be an object with only sources")
    contracts = {}
    for source, entry in sources.items():
        if (
            re.fullmatch(DATA_SOURCE_NAME, source) is None
            or not isinstance(entry, dict)
            or set(entry) != {"contract"}
            or not isinstance(entry["contract"], str)
            or re.fullmatch(DATA_CONTRACT_NAME, entry["contract"]) is None
        ):
            raise DataError(f"{path}: source {source!r} must record only a contract")
        contracts[source] = entry["contract"]
    return contracts


# (source, contract declaration, revision) → validation error. Every state reading
# re-reads each value file, and a large value costs far more to validate than to
# digest, so a server judges each distinct value once.
_JUDGED: dict[tuple[str, str, str], str | None] = {}


def _value_error(source: str, contract: str, value, revision: str, registry: dict):
    declaration = json.dumps(
        registry.get("$data", {}).get("contracts", {}).get(contract), sort_keys=True
    )
    key = source, declaration, revision
    if key not in _JUDGED:
        if len(_JUDGED) >= 1024:
            _JUDGED.clear()
        _JUDGED[key] = payload_error(source, contract, value, registry)
    return _JUDGED[key]


def _refuse_constant(name: str):
    """Python's reader accepts NaN and Infinity; JSON, and the browser, do not."""
    raise ValueError(f"{name} is not JSON")


def read_source(page_dir: Path, source: str, contract: str, registry: dict) -> dict:
    """One source as readers receive it: its contract, and, once a value file
    exists, that file's revision, `updated` instant, and `value` or `error`."""
    path = source_file(page_dir, source)
    try:
        data = path.read_bytes()
        modified = path.stat().st_mtime
    except FileNotFoundError:
        return {"contract": contract}
    reading = {
        "contract": contract,
        "revision": hashlib.sha256(data).hexdigest()[:16],
        "updated": datetime.fromtimestamp(modified)
        .astimezone()
        .isoformat(timespec="seconds"),
    }
    try:
        value = json.loads(data, parse_constant=_refuse_constant)
    except (UnicodeDecodeError, ValueError) as error:
        return {**reading, "error": f"source {source!r} is not JSON: {error}"}
    if error := _value_error(source, contract, value, reading["revision"], registry):
        return {**reading, "error": error}
    return {**reading, "value": value}


def read_data(page_dir: Path, registry: dict | None) -> dict:
    """Every recorded source, read and judged against `registry`.

    `version` digests the source revisions, so two readings of the same values
    compare equal whatever else changed between them. A page whose layer cannot be
    read has no contracts to judge its values by, and reads as holding none."""
    sources = (
        {
            source: read_source(page_dir, source, contract, registry)
            for source, contract in sorted(read_contracts(page_dir).items())
        }
        if registry is not None
        else {}
    )
    identity = json.dumps(
        {source: reading.get("revision") for source, reading in sources.items()}
    )
    return {
        "version": hashlib.sha256(identity.encode()).hexdigest()[:16],
        "sources": sources,
    }


def data_errors(stored: dict) -> list[str]:
    """Why each source whose current value fails its contract cannot be read."""
    return [
        reading["error"] for reading in stored["sources"].values() if "error" in reading
    ]


def deferred_records(value, contract: str, registry: dict) -> dict | None:
    """The contract's `records` declaration when this validated value's records
    carry a field Leaf delivers on demand (`records.deferred`).

    A contract may admit both an inline value and a record array. The deferred
    field applies only to an object carrying the declared item array.
    """
    spec = (
        registry.get("$data", {}).get("contracts", {}).get(contract, {}).get("records")
    )
    return (
        spec
        if spec is not None
        and "deferred" in spec
        and isinstance(value, dict)
        and isinstance(value.get(spec["items"]), list)
        else None
    )


def data_manifest(value, contract: str, registry: dict):
    """Keep a contract's records while leaving each deferred field at its source.

    Both browser delivery and agent inspection use this projection. It never
    mutates its input and returns the original value when nothing is deferred.
    """
    spec = deferred_records(value, contract, registry)
    if spec is None:
        return value
    return {
        **value,
        spec["items"]: [
            {key: item for key, item in record.items() if key != spec["deferred"]}
            for record in value[spec["items"]]
        ],
    }


def browser_data_from(stored: dict, registry: dict) -> dict:
    """The reading a browser receives: each value with its deferred fields omitted,
    which the fragment door serves from the same source file."""
    return {
        "version": stored["version"],
        "sources": {
            source: (
                {
                    **reading,
                    "value": data_manifest(
                        reading["value"], reading["contract"], registry
                    ),
                }
                if "value" in reading
                else reading
            )
            for source, reading in stored["sources"].items()
        },
    }


def data_fragment(
    reading: dict | None, registry: dict, *, source: str, revision: str, key: str
) -> dict:
    """One record's deferred field in the source value at `revision`, which must
    still be current.

    `reading` is the source as `read_source` read it, or None where the page records
    no such source."""
    if reading is None:
        raise DataError(f"unknown data source {source!r}")
    if reading.get("revision") != revision:
        raise StaleDataError(
            f"data source {source!r} no longer holds revision {revision!r}"
        )
    value = reading.get("value")
    spec = deferred_records(value, reading["contract"], registry)
    if spec is None:
        raise DataError(f"data source {source!r} defers no record field")
    matches = [
        item
        for item in value[spec["items"]]
        if isinstance(item, dict) and item.get(spec["key"]) == key
    ]
    if len(matches) != 1:
        reason = "unknown" if not matches else "duplicate"
        raise DataError(f"{reason} fragment key {key!r} in data source {source!r}")
    item = matches[0]
    if spec["deferred"] not in item:
        raise DataError(f"fragment {key!r} in data source {source!r} has no value")
    return {
        "source": source,
        "contract": reading["contract"],
        "revision": revision,
        "key": key,
        "value": item[spec["deferred"]],
    }


def _write_source(page_dir: Path, source: str, value) -> dict:
    """Validate and atomically replace one source's value, returning its reading."""
    try:
        # Validate the value the file will actually hold. Python's encoder accepts
        # values JSON itself cannot express directly — tuples become arrays and
        # non-string mapping keys become strings — so validating the
        # pre-serialization object can admit a value its own schema rejects on disk.
        value = json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError) as error:
        raise DataError(f"source {source!r} value is not JSON: {error}") from error
    if re.fullmatch(DATA_SOURCE_NAME, source) is None:
        raise DataError(f"invalid source name {source!r}")
    with PageTransaction(page_dir) as page:
        registry = read_page_registry(page_dir).registry
        bindings, binding_errors = working_data_bindings(
            page_dir, registry, page.events
        )
        if binding_errors:
            raise DataError(
                "the page history has conflicting data bindings: "
                + "; ".join(binding_errors)
            )
        contract = bindings.get(source)
        if contract is None:
            raise DataError(
                f"source {source!r} is not bound by the page source, a version, or "
                f"a thread widget; choose one of {sorted(bindings)}"
            )
        contracts = read_contracts(page_dir)
        recorded = contracts.get(source)
        if recorded is not None and recorded != contract:
            raise DataError(
                f"source {source!r} is now bound to contract {contract!r}, but it "
                f"was recorded with {recorded!r}; use a new source id for the new "
                "meaning"
            )
        if error := payload_error(source, contract, value, registry):
            raise DataError(error)
        writes = [(source_file(page_dir, source), json_bytes(value), False)]
        if recorded is None:
            contracts[source] = contract
            index = {
                "sources": {
                    name: {"contract": contracts[name]} for name in sorted(contracts)
                }
            }
            writes.append((page_dir / DATA_FILE, json_bytes(index), False))
        replace_files(writes)
        return read_source(page_dir, source, contract, registry)


def _report_write(verb: str, source: str, reading: dict) -> None:
    click.echo(
        f"{verb} data source {source!r} at revision {reading['revision']}, "
        f"updated {reading['updated']}"
    )


def cmd_data_set(page_dir: Path, source: str, value) -> None:
    """Validate and atomically replace one source's complete current value."""
    _report_write("set", source, _write_source(page_dir, source, value))


def cmd_data_capture(
    page_dir: Path,
    source: str,
    input_file: Path,
    lines: str | None = None,
    capture_format: str = "text",
) -> None:
    """Set one source from a UTF-8 file: whole, as a line range, or as a diff."""
    try:
        value = input_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise DataError(f"could not read {input_file}: {error}") from error
    if capture_format not in {"text", "unified-diff"}:
        raise DataError(f"unsupported capture format {capture_format!r}")
    if capture_format == "unified-diff":
        if lines is not None:
            raise DataError("lines can only select part of a text capture")
        value = unified_diff_manifest(value)
    if lines is not None:
        match = re.fullmatch(r"([1-9][0-9]*):([1-9][0-9]*)", lines)
        if match is None:
            raise DataError("lines must be a one-based inclusive START:END range")
        start = int(match.group(1))
        end = int(match.group(2))
        available = value.splitlines(keepends=True)
        if end < start or end > len(available):
            raise DataError(
                f"lines {lines} are outside {input_file}, which has "
                f"{len(available)} lines"
            )
        value = "".join(available[start - 1 : end])
    _report_write("captured", source, _write_source(page_dir, source, value))


def cmd_data_clear(page_dir: Path, source: str) -> None:
    """Remove one source's value; its id keeps the contract it was recorded with."""
    if re.fullmatch(DATA_SOURCE_NAME, source) is None:
        raise DataError(f"invalid source name {source!r}")
    with PageTransaction(page_dir):
        try:
            source_file(page_dir, source).unlink()
        except FileNotFoundError:
            click.echo(f"data source {source!r} is already clear")
            return
    click.echo(f"cleared data source {source!r}")
