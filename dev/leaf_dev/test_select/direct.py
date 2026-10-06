"""Exact changed symbol, source-range and resource witnesses.

These witnesses add tests to the mandatory selection. They never establish that
an unwitnessed test is unrelated. Source extraction shares the same Git index as
the cross-runtime evidence collector.
"""

import hashlib
import json
import re

from leaf_dev.test_select.javascript import javascript_records


def overlaps(start: int, end: int, hunks: list[dict], side: str) -> bool:
    return any(start <= h[side]["end"] and h[side]["start"] <= end for h in hunks)


class ChangePackets:
    def __init__(self, before, after):
        self.before, self.after = before, after
        self.base, self.candidate = before.ref, after.ref
        self.diff = self.after.git(
            "diff", "--no-renames", "--unified=0", self.base, self.candidate
        )
        self.diff_hash = hashlib.sha256(self.diff.encode()).hexdigest()
        self.hunks: dict[str, list] = {}
        path = None
        for line in self.diff.splitlines():
            if line.startswith("+++ b/"):
                path = line[6:]
                self.hunks.setdefault(path, [])
            elif line.startswith("--- a/"):
                old_path = line[6:]
                if old_path not in self.after.paths:
                    path = old_path
                    self.hunks.setdefault(path, [])
            elif line.startswith("@@ "):
                match = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))?", line)
                old, old_count, new, new_count = (
                    int(x) if x is not None else 1 for x in match.groups()
                )
                self.hunks[path].append(
                    {
                        "before": {"start": old, "end": old + max(0, old_count - 1)},
                        "after": {"start": new, "end": new + max(0, new_count - 1)},
                    }
                )
        self.changed_python_symbols = {
            (path, symbol)
            for path in self.hunks
            if path.endswith(".py")
            for symbol in before.changed_definition_symbols(after, path)
        }
        self.changed_python_imports = {
            path: before.changed_import_bindings(after, path)
            for path in self.hunks
            if path.endswith(".py")
        }
        self.changes = self.changed_definitions()
        self.changed_symbols = {
            (x["path"], x["symbol"]) for x in self.changes if x["symbol"]
        }

    def changed_definitions(self):
        result = []
        for side, index in [("before", self.before), ("after", self.after)]:
            js_paths = [
                p
                for p in self.hunks
                if p in index.paths
                and p.endswith((".js", ".mjs"))
                and "/vendor/" not in p
            ]
            js = {p: javascript_records(index.source(p), p) for p in js_paths}
            for path, hunks in self.hunks.items():
                if path not in index.paths:
                    continue
                source = index.source(path)
                found = []
                if path.endswith(".py"):
                    module = index.module(path)
                    for name, node in module["definitions"].items():
                        if (path, name) in self.changed_python_symbols:
                            found.append(
                                index.record(path, node, "changed-source", name)
                            )
                    for name in sorted(self.changed_python_imports[path]):
                        for _, node in module["import_declarations"].get(name, []):
                            found.append(
                                index.record(path, node, "changed-import", name)
                            )
                elif path in js:
                    for name, record in js[path]["definitions"].items():
                        if overlaps(record["start"], record["end"], hunks, side):
                            found.append(
                                {
                                    "path": path,
                                    "symbol": name,
                                    "kind": "changed-source",
                                    **record,
                                }
                            )
                if not found:
                    for hunk in hunks:
                        start = max(1, hunk[side]["start"] - 2)
                        end = min(len(source.splitlines()), hunk[side]["end"] + 2)
                        found.append(
                            {
                                "path": path,
                                "symbol": None,
                                "kind": "changed-hunk",
                                "start": start,
                                "end": end,
                                "code": "\n".join(source.splitlines()[start - 1 : end]),
                            }
                        )
                for record in found:
                    result.append(
                        {
                            **record,
                            "side": side,
                            "ref": self.base if side == "before" else self.candidate,
                            "sha256": hashlib.sha256(
                                record["code"].encode()
                            ).hexdigest(),
                        }
                    )
        return result

    def packet(self, item):
        evidence = self.after.extract(item)
        body = evidence["body"]
        result = {
            "nodeid": item["nodeid"],
            "body": body,
            "params": evidence["params"],
            "fixturenames": item.get("fixturenames", []),
            "change_witnesses": [],
            "evidence_missing": list(evidence["evidence_missing"]),
            "provenance": {
                "base": self.base,
                "candidate": self.candidate,
                "diff_sha256": self.diff_hash,
            },
        }
        strong = []
        readings = (("before", self.before.extract(item)), ("after", evidence))
        for side, reading in readings:
            self.add_witnesses(reading, side, strong)
        test_changed = bool(
            body
            and body["path"] in self.hunks
            and overlaps(body["start"], body["end"], self.hunks[body["path"]], "after")
        )
        if test_changed:
            strong.append(
                {
                    "kind": "changed-test-body",
                    "path": body["path"],
                    "symbol": body["symbol"],
                    "witness": {k: body[k] for k in ("path", "start", "end")},
                }
            )
        keys = set()
        for witness in strong:
            key = json.dumps(witness, sort_keys=True)
            if key not in keys:
                keys.add(key)
                result["change_witnesses"].append(witness)
        result["static_may_run"] = bool(result["change_witnesses"])
        return result

    def add_witnesses(self, evidence, side, strong):
        """Either immutable reading can witness a changed or deleted dependency."""
        for reference in evidence["refs"]:
            if (reference["path"], reference["symbol"]) in self.changed_symbols:
                strong.append(
                    {"kind": "exact-symbol-reference", "version": side, **reference}
                )
            elif (
                reference["symbol"] is None
                and reference["path"] in self.hunks
                and not any(p == reference["path"] for p, _ in self.changed_symbols)
            ):
                strong.append(
                    {"kind": "changed-module-reference", "version": side, **reference}
                )
        records = evidence["helpers"] + evidence["fixtures"] + evidence["probes"]
        for record in records + evidence["resources"]:
            path = record["path"]
            if path in self.hunks and (
                record.get("start") is None
                or (
                    (path, record.get("symbol")) in self.changed_python_symbols
                    if path.endswith(".py")
                    else overlaps(
                        record["start"], record["end"], self.hunks[path], side
                    )
                )
            ):
                strong.append(
                    {
                        "kind": "changed-resource"
                        if record.get("start") is None
                        else "changed-source-range",
                        "version": side,
                        "path": path,
                        "symbol": record.get("symbol"),
                        "witness": {
                            k: record[k]
                            for k in ("path", "start", "end")
                            if k in record
                        },
                    }
                )
