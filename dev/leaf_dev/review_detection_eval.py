"""Blinded UI review detection on frozen historical mechanism reconstructions.

Each run owns a fresh public-only fixture server, candidate packets and a snapshot
of its private rubric/provenance. Recognition supplies labelled screenshot sequences,
or candidate source text in the code-only condition; discovery supplies arrival only.
Code-only includes the pinned dependency source, without supplying rendered evidence.
Transition defects are unobservable to no-tools discovery and must not be scored as
misses. Promptfoo records raw answers; its
completion indicators are not correctness grades. Human scoring uses rubric.json.
"""

import hashlib
import json
import shutil
import subprocess
import sys
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
from leaf_dev.eval import PROMPTFOO

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
    for name in ("cases.yaml", "rubric.json", "provider.mjs"):
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
    """Evaluate UI review detection; every answer requires manual correctness scoring."""
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
    with served(output / "site") as origin:
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
            "description": f"UI review {mode}; raw answers require blind manual scoring",
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
                        "timeoutMs": 300000,
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
                "correctness": "manual scoring required",
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
            PROMPTFOO_DISABLE_TELEMETRY="1", PROMPTFOO_DISABLE_UPDATE_CHECK="1"
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
                "correctness": "unscored; apply rubric.json to raw answers",
                "no_tools_discovery_limit": "Transition-only failures are unobservable from arrival images and are excluded from miss rates.",
            },
        )
        if changed or result.returncode:
            raise click.ClickException(
                f"Run failed integrity/execution checks; inspect {output}"
            )
    click.echo(f"Raw results: {output / 'results.json'}; correctness remains unscored.")
