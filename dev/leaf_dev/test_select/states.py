"""Lossless bounded diff states with explicit generated-output provenance.

Tracked build manifests may declare output-to-source lineage; this replaces
redundant generated copies with their changed source inputs and hash witnesses.
It does not assert that a regeneration was correct. An unaccounted generated
change forces the broader all-tests selection instead of silently disappearing.
Ordinary changes, including documentation and test artifacts, remain in chunks.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from leaf_dev.test_select.evidence import test_function_name


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def provenance(before, after, changed, regeneration_proof=None):
    declared = {}
    for index, side in [(before, "before"), (after, "after")]:
        for path in sorted(p for p in index.paths if p.endswith("manifest.json")):
            try:
                manifest = json.loads(index.source(path))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if (
                not isinstance(manifest, dict)
                or not isinstance(manifest.get("outputs"), dict)
                or not isinstance(manifest.get("sourceInputs"), list)
            ):
                continue
            for output, metadata in manifest["outputs"].items():
                if output not in changed or output not in index.paths:
                    continue
                actual = digest(index.source(output))
                if not isinstance(metadata, dict) or metadata.get("sha256") != actual:
                    continue
                input_hashes = {
                    source: digest(index.source(source))
                    for source in manifest["sourceInputs"]
                    if source in index.paths
                }
                map_checks = []
                for map_path in manifest["outputs"]:
                    if not map_path.endswith(".map") or map_path not in index.paths:
                        continue
                    source_map = json.loads(index.source(map_path))
                    checked = []
                    mismatched = []
                    for source, content in zip(
                        source_map.get("sources", []),
                        source_map.get("sourcesContent", []),
                    ):
                        source_path = os.path.normpath(
                            str(Path(map_path).parent / source)
                        )
                        if source_path in index.paths:
                            checked.append(source_path)
                            if content != index.source(source_path):
                                mismatched.append(source_path)
                    map_checks.append(
                        {
                            "path": map_path,
                            "tracked_inputs_checked": checked,
                            "mismatched_inputs": mismatched,
                        }
                    )
                lockfile = manifest.get("lockfile")
                lock_valid = bool(
                    lockfile in index.paths
                    and digest(index.source(lockfile)) == manifest.get("lockfileSha256")
                )
                row = declared.setdefault(output, {})
                row[side] = {
                    "manifest": path,
                    "manifest_sha256": digest(index.source(path)),
                    "output_sha256": actual,
                    "output_hash_validated": True,
                    "tracked_input_sha256": input_hashes,
                    "source_map_input_checks": map_checks,
                    "lockfile_hash_validated": lock_valid,
                    "source_inputs": manifest["sourceInputs"],
                    "lockfile": manifest.get("lockfile"),
                    "lockfile_sha256": manifest.get("lockfileSha256"),
                }
    mapped = {}
    unknown = []
    for path in sorted(changed):
        generated = path.endswith(".map") or "/generated/" in path or "/vendor/" in path
        if not generated:
            continue
        sides = declared.get(path, {})
        inputs = {x for row in sides.values() for x in row["source_inputs"]}
        changed_inputs = sorted(inputs & changed)
        if (
            sides
            and changed_inputs
            and all(
                row["lockfile_hash_validated"]
                and not any(
                    check["mismatched_inputs"]
                    for check in row["source_map_input_checks"]
                )
                for row in sides.values()
            )
            and (path not in before.paths or "before" in sides)
            and (path not in after.paths or "after" in sides)
        ):
            proof_rows = (
                regeneration_proof.get("proofs", {}) if regeneration_proof else {}
            )
            rebuilt = True
            for index, side in [(before, "before"), (after, "after")]:
                ref = index.git("rev-parse", index.ref).strip()
                proof = proof_rows.get(ref, {})
                rebuilt = (
                    rebuilt
                    and proof.get("ref") == ref
                    and proof.get("install_exit") == 0
                    and proof.get("check_exit") == 0
                )
                if path in index.paths:
                    output = proof.get("outputs", {}).get(path, {})
                    expected = digest(index.source(path))
                    rebuilt = (
                        rebuilt
                        and output.get("verified") is True
                        and output.get("committed_sha256") == expected
                        and output.get("manifest_sha256") == expected
                        and output.get("checked_checkout_sha256") == expected
                        and output.get("rebuilt_sha256") == expected
                    )
            mapped[path] = {
                "status": "verified-regeneration"
                if rebuilt
                else "declared-source-lineage",
                "sides": sides,
                "changed_source_inputs": changed_inputs,
                "regeneration_verified": bool(rebuilt),
            }
        elif path.endswith("manifest.json") and "/generated/" in path:
            # Manifest itself is retained compactly, never treated as unexplained executable output.
            continue
        else:
            unknown.append(
                {
                    "path": path,
                    "reason": "generated change lacks hash-verified manifest lineage to changed tracked inputs",
                    "forced_selection": "all-tests",
                    "before_sha256": digest(before.source(path))
                    if path in before.paths
                    else None,
                    "after_sha256": digest(after.source(path))
                    if path in after.paths
                    else None,
                }
            )
    for path, row in mapped.items():
        if not row["regeneration_verified"]:
            unknown.append(
                {
                    "path": path,
                    "reason": "declared source lineage does not verify emitted behavior; immutable-ref regeneration absent",
                    "forced_selection": "all-tests",
                    "before_sha256": digest(before.source(path))
                    if path in before.paths
                    else None,
                    "after_sha256": digest(after.source(path))
                    if path in after.paths
                    else None,
                }
            )
    return mapped, unknown


def build_states(before, after, manifest, *, max_chars=45000, regeneration_proof=None):
    diff = after.git("diff", "--no-renames", "--unified=0", before.ref, after.ref)
    file_diffs = []
    current = None
    for line in diff.splitlines(keepends=True):
        if line.startswith("diff --git "):
            match = re.match(r"diff --git a/(.*?) b/(.*?)\n?$", line)
            current = {"path": match.group(2), "lines": [line]}
            file_diffs.append(current)
        elif current is not None:
            current["lines"].append(line)
    code_suffixes = (".py", ".js", ".mjs", ".ts", ".css", ".html")
    file_diffs.sort(
        key=lambda file: (
            file["path"].startswith("tests/"),
            not file["path"].endswith(code_suffixes),
            file["path"],
        )
    )
    changed = {x["path"] for x in file_diffs}
    if regeneration_proof is not None and not isinstance(regeneration_proof, dict):
        regeneration_proof = json.loads(Path(regeneration_proof).read_text())
    if regeneration_proof is not None and (
        regeneration_proof.get("schema") != "leaf-generated-rebuild-proof-v1"
        or set(regeneration_proof["proofs"]) != {before.ref, after.ref}
    ):
        raise ValueError("Regeneration proof identity/schema does not match case")
    mapped, unknown = provenance(before, after, changed, regeneration_proof)
    unknown_paths = {x["path"] for x in unknown}
    chunks = []
    covered = {}
    changed_test_paths = sorted(
        p for p in changed if p.startswith("tests/") or ".test." in p or ".spec." in p
    )
    for file in file_diffs:
        path = file["path"]
        if path in mapped and path not in unknown_paths:
            covered[path] = {
                "via": "declared-source-lineage"
                if path in mapped
                else "forced-all-tests"
            }
            continue
        header_lines = []
        pieces = []
        in_hunk = False
        for line in file["lines"]:
            if line.startswith("@@ "):
                in_hunk = True
            if not in_hunk and line.startswith(
                ("diff --git ", "index ", "--- ", "+++ ")
            ):
                header_lines.append(line)
            else:
                pieces.append(line)
        kind = "literal-unified-diff"
        # Serialized strings can expand up to twelve characters per Unicode
        # code point. Find the largest prefix that fits, preserving every byte.
        buffer = ""
        fragments = []
        for piece in pieces:
            remaining = piece
            while remaining:
                low, high = 1, len(remaining)
                fitting = 0
                while low <= high:
                    middle = (low + high) // 2
                    candidate = buffer + remaining[:middle]
                    if (
                        len(json.dumps({"path": path, "patch": candidate}))
                        <= max_chars - 500
                    ):
                        fitting = middle
                        low = middle + 1
                    else:
                        high = middle - 1
                if not fitting:
                    if not buffer:
                        raise ValueError(
                            "State budget cannot hold one serialized source character"
                        )
                    fragments.append(buffer)
                    buffer = ""
                    continue
                buffer += remaining[:fitting]
                remaining = remaining[fitting:]
                if remaining:
                    fragments.append(buffer)
                    buffer = ""
        if buffer:
            fragments.append(buffer)
        for position, text in enumerate(fragments):
            state = {
                "task": "Select tests relevant to this portion of the complete change; results are unioned across every portion.",
                "path": path,
                "fragment": position + 1,
                "fragments": len(fragments),
                "kind": kind,
                "patch": text,
            }
            assert len(json.dumps(state)) <= max_chars
            identifier = f"c{len(chunks)}"
            chunks.append(
                {
                    "id": identifier,
                    "state": state,
                    "state_chars": len(json.dumps(state)),
                    "sha256": digest(text),
                }
            )
        covered[path] = {
            "via": kind,
            "chunks": [x["id"] for x in chunks[-len(fragments) :]],
            "reassembled_sha256": digest("".join(fragments)),
            "literal_file_headers": header_lines,
            "literal_file_prelude": "".join(
                file["lines"][
                    : next(
                        (
                            i
                            for i, line in enumerate(file["lines"])
                            if line.startswith("@@ ")
                        ),
                        len(file["lines"]),
                    )
                ]
            ),
            "model_file_prelude": "".join(
                pieces[
                    : next(
                        (i for i, line in enumerate(pieces) if line.startswith("@@ ")),
                        len(pieces),
                    )
                ]
            ),
            "literal_file_patch_sha256": digest("".join(file["lines"])),
        }
        if kind == "literal-unified-diff":
            assert "".join(fragments) == "".join(pieces)
    assert set(covered) == changed
    # Pack independent file/function portions together; do not pay every test
    # question once per tiny changed file.
    groups = []
    old_to_group = {}
    current_parts = []
    current_old = []
    task = "Select tests relevant to this portion of the complete change; results are unioned across every portion."

    def finish_group():
        if not current_parts:
            return
        identifier = f"c{len(groups)}"
        state = {"task": task, "changes": list(current_parts)}
        groups.append(
            {
                "id": identifier,
                "state": state,
                "state_chars": len(json.dumps(state)),
                "sha256": digest(json.dumps(state, sort_keys=True)),
            }
        )
        for old in current_old:
            old_to_group[old] = identifier
        current_parts.clear()
        current_old.clear()

    for chunk in chunks:
        portion = {k: v for k, v in chunk["state"].items() if k != "task"}
        if (
            current_parts
            and len(json.dumps({"task": task, "changes": current_parts + [portion]}))
            > max_chars
        ):
            finish_group()
        current_parts.append(portion)
        current_old.append(chunk["id"])
    finish_group()
    for row in covered.values():
        if "chunks" in row:
            row["chunks"] = sorted({old_to_group[old] for old in row["chunks"]})
    for file in file_diffs:
        path = file["path"]
        headers = [line.rstrip() for line in file["lines"] if line.startswith("@@ ")]
        covered[path]["hunks"] = [
            {
                "id": f"{path}:h{i}",
                "header": header,
                "covered_by": covered[path]["via"],
                "chunks": covered[path].get("chunks", []),
            }
            for i, header in enumerate(headers)
        ]
        if path in mapped:
            covered[path]["source_chunks"] = sorted(
                {
                    c
                    for source in mapped[path]["changed_source_inputs"]
                    for c in covered[source].get("chunks", [])
                }
            )
    chunks = groups
    assert all(x["state_chars"] <= max_chars for x in chunks)
    zero_hunks = {}
    path = None
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
            zero_hunks.setdefault(path, [])
        elif line.startswith("@@ "):
            match = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))?", line)
            start = int(match.group(1))
            count = int(match.group(2) or 1)
            zero_hunks.setdefault(path, []).append((start, start + max(0, count - 1)))
    auto_run = []
    for item in manifest:
        path = item["file"]
        if path not in changed_test_paths or path not in after.paths:
            continue
        if path.endswith(".py"):
            name = test_function_name(item)
            node = after.definition(path, name, line=item.get("line"))
            if node and any(
                min([node.lineno] + [d.lineno for d in node.decorator_list]) <= end
                and start <= node.end_lineno
                for start, end in zero_hunks.get(path, [])
            ):
                auto_run.append(item["nodeid"])
        else:
            auto_run.append(item["nodeid"])
    return {
        "schema": "leaf-change-states-v1",
        "base": before.git("rev-parse", before.ref).strip(),
        "candidate": after.git("rev-parse", after.ref).strip(),
        "diff_sha256": digest(diff),
        "state_chunks": chunks,
        "source_provenance": mapped,
        "unknown_generated": unknown,
        "forced_all_tests": bool(unknown),
        "changed_test_paths": changed_test_paths,
        "auto_run_test_ids": auto_run,
        "coverage": covered,
        "metrics": {
            "original_diff_chars": len(diff),
            "states": len(chunks),
            "max_state_chars": max((x["state_chars"] for x in chunks), default=0),
            "state_chars_total": sum(x["state_chars"] for x in chunks),
            "mapped_generated": len(mapped),
            "unknown_generated": len(unknown),
        },
    }
