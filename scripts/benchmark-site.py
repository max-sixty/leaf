#!/usr/bin/env python3
"""Measure one Leaf page, comment, requested edit, publication, and reply journey."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
LOCAL_RUNNER = ROOT / "scripts" / "verify-site-agent-local.sh"
VERIFY_SITE = ROOT / "scripts" / "verify-site.py"
RELEASE = re.compile(r"[0-9a-f]{64}")


def load_verifier():
    """Load the shared browser journey after its target origin is configured."""
    spec = importlib.util.spec_from_file_location("verify_site_benchmark", VERIFY_SITE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {VERIFY_SITE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def measure(release: str | None) -> dict:
    """Run the endpoint-independent browser journey against the configured origin."""
    verifier = load_verifier()
    with verifier.sync_playwright() as playwright:
        browser, browser_name = verifier.launch_browser(playwright)
        try:
            result = verifier.verify_agent_turn(browser, release, report=False)
        finally:
            browser.close()
    return {"browser": browser_name, **result}


def measure_local() -> dict:
    """Provision the canonical local adapter, then let it run this same journey."""
    with tempfile.TemporaryDirectory(prefix="leaf-site-benchmark.") as temporary:
        output = Path(temporary) / "result.json"
        environment = {
            **os.environ,
            "LEAF_SITE_AGENT_RUNNER": str(Path(__file__).resolve()),
            "LEAF_BENCHMARK_OUTPUT": str(output),
        }
        completed = subprocess.run(
            [str(LOCAL_RUNNER)],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode:
            sys.stderr.write(completed.stdout)
            sys.stderr.write(completed.stderr)
            raise SystemExit(completed.returncode)
        return json.loads(output.read_text(encoding="utf-8"))


def configure_origin(target: str) -> None:
    """Validate and configure an HTTP endpoint before loading the verifier module."""
    parsed = urlsplit(target)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SystemExit("target must be `local` or an http(s) origin")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise SystemExit(
            "target URL must be an origin without a path, query, or fragment"
        )
    os.environ["LEAF_SITE_ORIGIN"] = target.rstrip("/")


def main() -> None:
    """Measure local Leaf or any deployed Leaf origin, emitting one JSON sample."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "target",
        metavar="local|ORIGIN",
        help="start the canonical local adapter, or measure an existing HTTP origin",
    )
    target = parser.parse_args().target
    if target == "local":
        result = measure_local()
    elif RELEASE.fullmatch(target):
        result = measure(target)
        output = os.environ.get("LEAF_BENCHMARK_OUTPUT")
        if output is not None:
            Path(output).write_text(json.dumps(result), encoding="utf-8")
            return
    else:
        configure_origin(target)
        result = measure(None)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
