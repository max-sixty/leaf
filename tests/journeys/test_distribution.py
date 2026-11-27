"""The website's prepared install needs no compiler, including for custom packages.

Exercise the actual copied launcher, kernel, render probes and offline document.
Compiler shims fail every attempted Node/package-manager invocation after preparation.
"""

import json
import os
import subprocess

from interact_support import PAGE, PAGE_GROUP
from playwright.sync_api import expect

from leaf_dev import ROOT
from leaf_dev.arms import environment
from leaf_dev.commands.site._distribution import prepare


def test_prepared_install_authors_custom_packages_and_exports_without_builds(
    tmp_path, spawn, request
):
    install = tmp_path / "install"
    prepare(install)
    assert (install / "LICENSE").read_bytes() == (ROOT / "LICENSE").read_bytes()
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    for name in ("node", "npm", "npx", "pnpm"):
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
    (custom / "runtime/helpers").mkdir(parents=True)
    (custom / "runtime/helpers/État+v1.mjs").write_text(
        'export * from "/runtime/widget-api.js";\n'
    )
    widget = custom / "widgets/lf-risk-note.js"
    widget.write_text('import "/runtime/helpers/État+v1.mjs";\n' + widget.read_text())
    leaf("package", "check", "custom")
    page_dir = tmp_path / "page"
    leaf(
        "page",
        "init",
        "--package",
        "reading",
        "--package",
        "./custom",
        "--package",
        "diagram",
        "--package",
        "playground",
        page_dir,
    )
    source = PAGE.replace(PAGE_GROUP, '<lf-options id="plan-options">').replace(
        "<h2>Plan</h2>",
        '<h2>Plan</h2><lf-risk-note id="risk"></lf-risk-note>',
    )
    source = source.replace(
        "</main>",
        '<lf-group id="prepared-q" label="Which label?">'
        '<lf-playground id="prepared-playground">'
        '<aside><label id="label">Label <input name="label" '
        'value="Prepared"></label></aside>'
        "<p>Native initial drawing works.</p>"
        "<lf-playground-output>Use "
        '<output for="label"></output>.'
        "</lf-playground-output></lf-playground></lf-group></main>",
    )
    (page_dir / "index.html").write_text(source)
    leaf("page", "check", page_dir, "--render")
    leaf("page", "stamp", page_dir, "--text", "Prepared installation verified")
    exported = tmp_path / "export.html"
    server = spawn(
        [
            str(install / "bin/leaf"),
            "server",
            "run",
            "--lifetime",
            "temporary",
            str(page_dir),
        ],
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
            leaf("page", "export", page_dir, "--out", exported, "--runtime")
        tab = browser.new_page()
        tab.goto(target)
        expect(tab.locator("body")).to_have_attribute("data-lf-presented", "1")
        # The custom package's starter widget draws its choices.
        expect(
            tab.locator("lf-risk-note").get_by_role("button", name="Yes")
        ).to_be_visible()
        playground = tab.locator("#prepared-playground")
        expect(playground.locator("input[name=label]")).to_have_value("Prepared")
        expect(playground.locator("lf-playground-output")).to_contain_text(
            "Use Prepared."
        )
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
    replacement = custom / "runtime/state/context.js"
    replacement.parent.mkdir()
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
        assert (
            "replaces private kernel modules: runtime/state/context.js"
            in refused.stdout
        )
