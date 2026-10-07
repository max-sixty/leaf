"""A prepared install needs no compiler, including native custom-package authoring.

Exercise the actual copied launcher, kernel, render probes and offline document.
Compiler shims fail every attempted node/npm invocation after CI preparation.
"""

import json
import os
import subprocess

import pytest
from click import ClickException
from interact_support import PAGE
from leaf_dev import ROOT
from leaf_dev import distribution as distribution_model
from leaf_dev.arms import environment
from leaf_dev.distribution import prepare
from playwright.sync_api import expect


def test_prepared_install_authors_custom_packages_and_exports_without_builds(
    tmp_path, spawn, request
):
    install = tmp_path / "install"
    prepare(install)
    assert (install / "LICENSE").read_bytes() == (ROOT / "LICENSE").read_bytes()
    manifest = json.loads((install / "package.json").read_text())
    assert "devDependencies" not in manifest
    assert "scripts" not in manifest
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    for name in ("node", "npm", "npx"):
        shim = blocked / name
        shim.write_text("#!/bin/sh\necho 'unexpected consumer compiler' >&2\nexit 91\n")
        shim.chmod(0o755)
    state = tmp_path / "state"
    consumer_env = environment(
        XDG_STATE_HOME=str(state),
        PATH=f"{blocked}{os.pathsep}{os.environ['PATH']}",
    )

    def leaf(*args):
        result = subprocess.run(
            [str(install / "bin/leaf"), *map(str, args)],
            cwd=tmp_path,
            env=consumer_env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout

    leaf("package", "init", "custom", "--widget", "lf-risk-note")
    custom = tmp_path / "custom"
    (custom / "runtime/custom-helper.js").write_text(
        'export { once } from "/runtime/widget-api.js";\n'
    )
    widget = custom / "widgets/lf-risk-note.js"
    widget.write_text(
        widget.read_text().replace(
            "/runtime/widget-api.js", "/runtime/custom-helper.js"
        )
    )
    leaf("package", "check", "custom")
    page_dir = tmp_path / "page"
    leaf("page", "init", "--package", "./custom", "--package", "diagram", page_dir)
    source = PAGE.replace(
        "<lf-options>", '<lf-options id="plan-options" choose>'
    ).replace(
        "<h2>Plan</h2>",
        '<h2>Plan</h2><lf-risk-note id="risk">Custom package works.</lf-risk-note>',
    )
    (page_dir / "index.html").write_text(source)
    leaf("page", "check", page_dir, "--render")
    leaf("page", "stamp", page_dir, "--text", "Prepared installation verified")
    exported = tmp_path / "export.html"
    server = spawn(
        [str(install / "bin/leaf"), "server", "run", "--temporary", str(page_dir)],
        env=consumer_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    address = json.loads(server.stdout.readline())["url"]
    # Acquire the browser after spawn so fixture teardown ends the clients first.
    browser = request.getfixturevalue("browser")
    for target in (address, exported.as_uri()):
        if target != address:
            leaf("page", "export", page_dir, "--out", exported)
        tab = browser.new_page()
        tab.goto(target)
        expect(tab.locator("body")).to_have_attribute("data-lf-presented", "1")
        expect(tab.locator("lf-risk-note")).to_have_text("Custom package works.")
        assert tab.evaluate("customElements.get('lf-risk-note') !== undefined")
        choice = tab.locator("#flag-first .lf-pick")
        if target == address:
            with tab.expect_response(
                lambda response: (
                    response.url.split("?")[0].endswith("/api/event")
                    and response.request.method == "POST"
                )
            ) as admitted:
                choice.click()
            assert admitted.value.ok
            expect(choice).to_have_attribute("aria-checked", "true")
        else:
            # A stamped offline version is a read-only historical document.
            expect(choice).to_have_attribute("aria-disabled", "true")
            expect(choice).to_have_attribute("aria-checked", "true")
    # Both source and prepared installations reject the same private override.
    replacement = custom / "runtime/context.js"
    replacement.write_text("export const privateState = {};\n")
    for runtime in (ROOT, install):
        refused = subprocess.run(
            [str(runtime / "bin/leaf"), "package", "check", str(custom)],
            cwd=tmp_path,
            env=consumer_env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert refused.returncode != 0
        assert "replaces private kernel modules: runtime/context.js" in refused.stderr


def test_prepared_publication_preserves_source_ancestry_and_rejects_stale_builds(
    tmp_path, monkeypatch
):
    """Use a real local Git remote; publication never edits the source index."""
    source = tmp_path / "source"
    remote = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", str(remote)], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "init", "-b", "main", str(source)], check=True, capture_output=True
    )

    def git(*args):
        return subprocess.run(
            ["git", "-C", str(source), *args],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    git("config", "user.name", "Distribution test")
    git("config", "user.email", "distribution@example.test")
    git("remote", "add", "origin", str(remote))
    (source / "source.txt").write_text("first\n")
    git("add", ".")
    git("commit", "-m", "First source")
    git("push", "origin", "main")
    first = git("rev-parse", "HEAD")
    monkeypatch.setattr(distribution_model, "PLUGIN_ROOT", source)
    payload = tmp_path / "payload"
    payload.mkdir()
    (payload / "compiled.js").write_text("compiled output\n")
    metadata = payload / "leaf-distribution.json"

    def stamp(commit, dirty=False):
        metadata.write_text(
            json.dumps({"producer": {"commit": commit, "dirty": dirty}})
        )

    stamp(first)
    source_index = git("write-tree")
    prepared_first = distribution_model.publish(payload)
    assert git("write-tree") == source_index
    assert git("show", f"{prepared_first}:compiled.js") == "compiled output"
    git("merge-base", "--is-ancestor", first, prepared_first)
    assert distribution_model.publish(payload) == prepared_first

    (source / "source.txt").write_text("second\n")
    git("add", ".")
    git("commit", "-m", "Second source")
    git("push", "origin", "main")
    second = git("rev-parse", "HEAD")
    assert distribution_model.publish(payload) is None
    stamp(second)
    prepared_second = distribution_model.publish(payload)
    git("merge-base", "--is-ancestor", prepared_first, prepared_second)
    git("merge-base", "--is-ancestor", second, prepared_second)
    assert "compiled.js" not in git("ls-tree", "--name-only", "main")
    stamp(second, dirty=True)
    with pytest.raises(ClickException, match="dirty"):
        distribution_model.publish(payload)


@pytest.mark.parametrize("directory", ["runtime", "widgets", "vendor"])
@pytest.mark.parametrize("suffix", [".js", ".mjs"])
def test_package_private_imports_are_refused(directory, suffix, tmp_path):
    """Every package browser directory shares the public kernel boundary."""
    from leaf.layer import compose_layer, layer_inputs

    custom = tmp_path / "custom"
    (custom / directory).mkdir(parents=True)
    (custom / directory / f"helper{suffix}").write_text(
        'export { runtime } from "/runtime/context.js";\n'
    )
    with pytest.raises(SystemExit, match="imports private kernel module"):
        compose_layer([*layer_inputs(), custom])
