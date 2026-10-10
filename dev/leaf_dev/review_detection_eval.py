"""Blinded UI review detection on frozen historical mechanism reconstructions.

Each run owns a fresh public-only fixture server, candidate packets and a snapshot
of its private rubric/provenance. Recognition supplies labelled screenshot sequences,
or candidate source text in the code-only condition; discovery supplies arrival only.
Code-only includes the pinned dependency source, without supplying rendered evidence.
Transition defects are unobservable to no-tools discovery and must not be scored as
misses. Promptfoo grades completed answers through an evidence-aware JavaScript
assertion using its standard isolated Codex judge. The frozen rubric owns target
meaning; transport and judge failures remain unscored rather than review misses.
"""

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from datetime import UTC, datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from importlib.metadata import version
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import urlopen

import click
import yaml
from playwright.sync_api import expect

from leaf_dev import ROOT
from leaf_dev.arms import environment
from leaf_dev.browser import chrome
from leaf_dev.eval import PROMPTFOO, screenshot_judge

SOURCE = ROOT / "evals/ui-review-detection"
MODELS = {
    "sol": "gpt-6.1-sol",
    "opus": "claude-opus-5-5",
    "fable": "claude-fable-5-1",
    "astra": "gpt-6-astra",
}
CASES = {
    "timeline": "recording-times",
    "shift": "recording-stepping",
}


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@contextmanager
def served(site):
    """Expose only staged public files; directory listings and private paths fail."""

    class Handler(SimpleHTTPRequestHandler):
        def list_directory(self, _):
            self.send_error(404)

        def log_message(self, *_):
            pass

    with ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(Handler, directory=str(site))
    ) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}"
        finally:
            server.shutdown()
            thread.join()


def capture(browser, origin, variant, identity, output, mode, *, include_images=True):
    """Assert the historical contrast and capture neutral, ordered observations."""
    family = variant.split("-", 1)[0]
    page = browser.new_page(
        viewport={"width": 1200, "height": 900}, reduced_motion="reduce"
    )
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(f"{origin}/{identity}.html")
    page.wait_for_function("window.__fixtureReady === true")
    images, labels = [], []

    def screenshot(label):
        if not include_images:
            return
        file = f"view-{len(images)}.png"
        page.screenshot(path=output / file)
        images.append(file)
        labels.append(label)

    screenshot("Initial view")
    row = {"variant": variant, "errors": errors}
    if family == "timeline":
        expect(page.locator(".vis-item.vis-box")).to_have_count(9)
        assert all(
            node.is_visible() for node in page.locator(".vis-item.vis-box").all()
        )
        assert page.locator(".vis-text.vis-minor").count() >= 5
        visible = sum(node.is_visible() for node in page.locator(".vis-dot").all())
        assert visible == (0 if variant.endswith("defect") else 9)
        page.get_by_role("button", name="Press t · 1.650 s", exact=True).click()
        screenshot("After selecting the later t input marker")
        row.update(visible_anchors=visible, after=page.locator("#readout").inner_text())
        assert "1.650 s" in row["after"]
    else:
        widget = page.locator("lf-trace")
        image = widget.locator("img")
        expect(image).to_be_visible()
        before = image.bounding_box()
        widget.get_by_role("checkbox", name="Show intermediate frames").check()
        screenshot("After enabling Show intermediate frames")
        widget.get_by_role("button", name="Next", exact=True).click()
        screenshot("After activating Next once")
        after = image.bounding_box()
        shift = after["y"] - before["y"]
        assert abs(shift) > 20 if variant.endswith("defect") else abs(shift) < 0.1
        row.update(before=before, after=after, shift_px=shift)
    assert "undefined" not in page.locator("body").inner_text()
    assert not errors, errors
    page.close()
    if mode == "discovery":
        images, labels = images[:1], labels[:1]
    write_json(
        output / "input.json",
        {
            "prompt": "request.md",
            "images": images,
            "evidenceLabels": labels,
            "url": f"{origin}/{identity}.html",
        },
    )
    return row


def stage(output):
    """Check the frozen input hashes before copying any candidate assets."""
    fixtures = SOURCE / "fixtures"
    provenance = json.loads((fixtures / "private/provenance.json").read_text())
    for name, expected in provenance["sha256"].items():
        if digest(fixtures / name) != expected:
            raise click.ClickException(f"Frozen fixture changed: {name}")
        target = output / "site" / Path(name).relative_to("public")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(fixtures / name, target)
    dependency = ROOT / provenance["dependency"]["path"]
    if digest(dependency) != provenance["dependency"]["sha256"]:
        raise click.ClickException("Frozen timeline dependency changed")
    shutil.copyfile(dependency, output / "site/assets/timeline.esm.js")
    for name in ("cases.yaml", "rubric.json", "provider.mjs", "grade.mjs"):
        shutil.copyfile(SOURCE / name, output / name)
    shutil.copyfile(fixtures / "private/provenance.json", output / "provenance.json")
    shutil.copyfile(Path(__file__), output / "runner.py")
    for name in ("package.json", "package-lock.json"):
        shutil.copyfile(ROOT / "evals" / name, output / f"dependency-{name}")
    dependencies = json.loads((ROOT / "evals/package.json").read_text())["dependencies"]
    installed = {
        name: json.loads(
            (ROOT / "evals/node_modules" / name / "package.json").read_text()
        )["version"]
        for name in dependencies
    }
    if installed != dependencies:
        raise click.ClickException(
            "Installed eval dependencies differ; run npm ci in evals"
        )
    write_json(
        output / "environment.json",
        {
            "node": subprocess.check_output(
                ["node", "--version"], text=True, env=environment()
            ).strip(),
            "python": sys.version,
            "python_playwright": version("playwright"),
            "installed_direct_dependencies": installed,
            "installation_limit": "Lock retained; transitive installed bytes are not independently hashed.",
        },
    )
    (output / "node_modules").symlink_to(ROOT / "evals/node_modules")
    return provenance


def grading(output, home):
    """Configure the standard judge on anonymous evidence, with a disposable home.

    The login home stays outside the evidence tree. Candidate providers read only
    their task/manifest; private assertion metadata never enters their request.
    """
    evidence = output / "grading"
    evidence.mkdir()
    provider = screenshot_judge(None, home)
    write_json(
        output / "grader-environment.json",
        {
            "provider": provider["id"],
            "model": provider["config"]["model"],
            "codex": subprocess.check_output(
                [provider["config"]["codex_path_override"], "--version"],
                text=True,
                env=environment(),
            ).strip(),
        },
    )
    return {
        "metadata": {
            "graderProvider": provider,
            "gradingDir": str(evidence),
            "rubricFile": str(output / "rubric.json"),
        },
        "assert": [
            {
                "type": "javascript",
                "value": (output / "grade.mjs").as_uri(),
                "metric": "ui-review",
            }
        ],
    }


def summarize(output):
    """Derive outcomes from Promptfoo's export, excluding unscored denominators."""
    exported = json.loads((output / "results.json").read_text())
    rows = []
    for result in exported["results"]["results"]:
        metadata = result["testCase"]["metadata"]
        components = (result.get("gradingResult") or {}).get("componentResults", [])
        grade = next(
            (
                component["metadata"]["grade"]
                for component in components
                if "grade" in component.get("metadata", {})
            ),
            None,
        )
        rows.append(
            {
                "case": metadata["privateCase"],
                "variant": metadata["privateVariant"],
                "provider": result["provider"]["label"],
                "sample": result["response"].get("metadata", {}).get("evidenceDir"),
                "grade": grade,
                "scorable": grade is not None and grade["scorable"],
                "error": result.get("error") if grade is None else None,
            }
        )
    scored = [row for row in rows if row["scorable"]]
    defects = [row["grade"] for row in scored if row["variant"].endswith("defect")]
    controls = [row["grade"] for row in scored if row["variant"].endswith("control")]
    summary = {
        "samples": len(rows),
        "scored": len(scored),
        "unscored": len(rows) - len(scored),
        "defects": len(defects),
        "detected": sum(grade["target_detection"] == 2 for grade in defects),
        "concerns": sum(grade["target_detection"] == 1 for grade in defects),
        "missed": sum(grade["target_detection"] == 0 for grade in defects),
        "controls": len(controls),
        "target_false_alarms": sum(grade["target_false_alarm"] for grade in controls),
        "unsupported_observations": sum(
            len(row["grade"]["unsupported_observations"]) for row in scored
        ),
        "rows": rows,
    }
    write_json(output / "grading-summary.json", summary)
    return summary


@click.command("eval-ui-review")
@click.option(
    "--model",
    "models",
    multiple=True,
    type=click.Choice(list(MODELS)),
    default=("sol",),
)
@click.option(
    "--condition",
    type=click.Choice(["no-tools", "browser", "both", "code-only"]),
    default="both",
)
@click.option(
    "--mode", type=click.Choice(["recognition", "discovery"]), default="recognition"
)
@click.option("--repeat", type=click.IntRange(min=1), default=1)
@click.option(
    "--prepare-only",
    is_flag=True,
    help="Verify/capture/configure without calling a model.",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    help="Fresh directory; defaults under .tmp/eval-ui-review/.",
)
def eval_ui_review(models, condition, mode, repeat, prepare_only, output):
    """Evaluate and grade UI review detection against frozen defect/control pairs."""
    if condition == "code-only" and mode == "discovery":
        raise click.UsageError(
            "Code-only reviews source; discovery requires visual evidence."
        )
    default = (
        ROOT
        / ".tmp/eval-ui-review"
        / datetime.now(UTC).strftime("run-%Y%m%d-%H%M%S-%f")
    )
    output = (output or default).resolve()
    if output.exists():
        raise click.ClickException(f"Output directory already exists: {output}")
    output.mkdir(parents=True)
    provenance = stage(output)
    cases = yaml.safe_load((output / "cases.yaml").read_text())["cases"]
    conditions = ["no-tools", "browser"] if condition == "both" else [condition]
    with (
        tempfile.TemporaryDirectory(prefix="leaf-ui-grader-") as temporary,
        served(output / "site") as origin,
    ):
        for private in (
            "/private/provenance.json",
            "/../rubric.json",
            "/provenance.json",
            "/",
        ):
            try:
                urlopen(origin + private)
            except HTTPError as error:
                assert error.code == 404
            else:
                raise click.ClickException(
                    f"Private fixture path was exposed: {private}"
                )
        tests, readings = [], {}
        with chrome() as browser:
            runtime = json.loads((output / "environment.json").read_text())
            runtime["chrome"] = browser.version
            write_json(output / "environment.json", runtime)
            for variant, identity in provenance["variants"].items():
                packet = output / "candidates" / identity
                packet.mkdir(parents=True)
                family = variant.split("-", 1)[0]
                prompt = cases[CASES[family]]["prompt"]
                (packet / "request.md").write_text(prompt)
                readings[identity] = capture(
                    browser,
                    origin,
                    variant,
                    identity,
                    packet,
                    mode,
                    include_images=condition != "code-only",
                )
                if condition == "code-only":
                    case = cases[CASES[family]]
                    sources = []
                    for template in case["source_files"]:
                        name = template.format(candidate=identity)
                        target = packet / "source" / name
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(output / "site" / name, target)
                        sources.append({"path": name, "file": f"source/{name}"})
                    write_json(
                        packet / "input.json",
                        {
                            "prompt": "request.md",
                            "images": [],
                            "sources": sources,
                        },
                    )
                tests.append(
                    {
                        "description": identity,
                        "vars": {
                            "prompt": prompt,
                            "manifest": str(packet / "input.json"),
                        },
                        "metadata": {
                            "privateCase": CASES[family],
                            "privateVariant": variant,
                            "mode": mode,
                            "noToolsTargetUnobservable": mode == "discovery"
                            and family == "shift",
                        },
                    }
                )
        write_json(output / "behavior-evidence.json", readings)
        config = {
            "description": f"UI review {mode}; automatic blinded evidence-aware grading",
            "defaultTest": grading(output, Path(temporary) / "judge"),
            "prompts": ["{{prompt}}"],
            "providers": [
                {
                    "id": str(output / "provider.mjs"),
                    "label": f"{model}/{arm}",
                    "config": {
                        "model": MODELS[model],
                        "condition": arm,
                        "effort": "high",
                        "toolBudget": 12,
                        "evidenceDir": str(output / "samples"),
                    },
                }
                for model in models
                for arm in conditions
            ],
            "tests": tests,
            "evaluateOptions": {"maxConcurrency": 2, "showProgressBar": False},
        }
        write_json(output / "promptfooconfig.json", config)
        write_json(
            output / "run.json",
            {
                "models": models,
                "condition": condition,
                "mode": mode,
                "repeat": repeat,
                "prepare_only": prepare_only,
                "private_paths_returned_404": True,
                "correctness": "automatic model-anonymous rubric grading",
                "no_tools_discovery_limit": "Transition-only targets are unobservable from arrival images; exclude them from miss rates.",
            },
        )
        frozen = {
            file.relative_to(output).as_posix(): digest(file)
            for file in output.rglob("*")
            if file.is_file() and "node_modules" not in file.parts
        }
        write_json(output / "frozen-hashes.json", frozen)
        click.echo(
            f"Prepared {len(tests)} candidates × {len(config['providers'])} providers × {repeat} repeats: {output}"
        )
        if prepare_only:
            click.echo(
                "Preparation verified. Its owned fixture server is now closing; run this command without --prepare-only for inference."
            )
            return
        env = environment(
            PROMPTFOO_DISABLE_TELEMETRY="1",
            PROMPTFOO_DISABLE_UPDATE_CHECK="1",
            PROMPTFOO_EVAL_TIMEOUT_MS="0",
            PROMPTFOO_MAX_EVAL_TIME_MS="0",
            PROMPTFOO_FAILED_TEST_EXIT_CODE="100",
        )
        for key in (
            "OPENAI_API_KEY",
            "CODEX_API_KEY",
            "ANTHROPIC_API_KEY",
            "CLAUDE_CONFIG_DIR",
        ):
            env.pop(key, None)
        result = subprocess.run(
            [
                str(PROMPTFOO),
                "eval",
                "-c",
                str(output / "promptfooconfig.json"),
                "--repeat",
                str(repeat),
                "--no-cache",
                "--no-share",
                "--max-concurrency",
                "2",
                "-o",
                str(output / "results.json"),
            ],
            cwd=ROOT / "evals",
            env=env,
            stdin=subprocess.DEVNULL,
            check=False,
        )
        changed = [
            name
            for name, expected in frozen.items()
            if digest(output / name) != expected
        ]
        write_json(
            output / "integrity.json",
            {
                "changed_inputs": changed,
                "returncode": result.returncode,
                "correctness": "see results.json and grading-summary.json",
                "no_tools_discovery_limit": "Transition-only failures are unobservable from arrival images and are excluded from miss rates.",
            },
        )
        if changed or result.returncode not in (0, 100):
            raise click.ClickException(
                f"Run failed integrity/execution checks; inspect {output}"
            )
        summary = summarize(output)
        click.echo(
            f"Graded {summary['scored']}/{summary['samples']}; "
            f"detected {summary['detected']}/{summary['defects']} defects "
            f"({summary['concerns']} partial, {summary['missed']} missed); "
            f"{summary['target_false_alarms']}/{summary['controls']} control false alarms; "
            f"{summary['unsupported_observations']} unsupported observations; "
            f"{summary['unscored']} unscored."
        )
    click.echo(f"Results: {output / 'results.json'}\nview: npm run view --prefix evals")
    if result.returncode:
        raise click.exceptions.Exit(result.returncode)
