"""Prepared installations retain the package boundary and follow runtime inputs.

The compiler-free installation journey lives in the journey suite. These readings
cover package admission and cache invalidation without booting a browser or compiler.
"""

import json
import subprocess

import pytest
from leaf.refusals import Refused
from leaf_dev import distribution


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
    with pytest.raises(Refused, match="imports private kernel module"):
        compose_layer([*layer_inputs(), custom])


def test_compiled_cache_follows_payload_and_compiler_bytes(tmp_path, monkeypatch):
    """Identical saves and authored revisions reuse a kernel; its inputs do not."""
    monkeypatch.setattr(distribution, "ROOT", tmp_path)
    module = tmp_path / "skills/leaf/assets/runtime/example.js"
    compiler = tmp_path / "build/runtime-bundle.mjs"
    authored = tmp_path / "examples/page.html"
    for path, content in (
        (module, "export const example = 1;"),
        (compiler, "compileKernel();"),
        (authored, "<p>First draft</p>"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    original = distribution.installation_identity(tmp_path)
    module.touch()
    authored.write_text("<p>Revised draft</p>")
    assert distribution.installation_identity(tmp_path) == original
    module.write_text("export const example = 2;")
    changed_runtime = distribution.installation_identity(tmp_path)
    assert changed_runtime != original
    compiler.write_text("compileKernelDifferently();")
    assert distribution.installation_identity(tmp_path) != changed_runtime


def test_compiled_cache_reuses_bytes_while_refreshing_git_provenance(
    tmp_path, monkeypatch
):
    """Authored edits and commits update the producer without another compiler run."""
    monkeypatch.setattr(distribution, "ROOT", tmp_path)

    def git(*args):
        subprocess.run(
            [
                "git",
                "-C",
                str(tmp_path),
                "-c",
                "user.name=Leaf Test",
                "-c",
                "user.email=leaf@example.test",
                "-c",
                "commit.gpgsign=false",
                *args,
            ],
            check=True,
            capture_output=True,
            text=True,
        )

    module = tmp_path / "skills/leaf/assets/runtime/example.js"
    authored = tmp_path / "examples/page.html"
    for path, content in (
        (module, "export const example = 1;"),
        (authored, "<p>First draft</p>"),
        (tmp_path / ".gitignore", ".tmp/\n"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    git("init")
    git("add", ".")
    git("commit", "-m", "First runtime")
    preparations = []

    def prepare(output):
        # This test owns cache orchestration. The real compiler and page launcher
        # are exercised by the prepared-installation journey.
        preparations.append(output)
        bundle = output / "runtime/bundle.js"
        bundle.parent.mkdir(parents=True)
        bundle.write_bytes(module.read_bytes())
        (output / "leaf-distribution.json").write_text(
            json.dumps(
                {
                    "producer": distribution.payload_provenance(root=tmp_path),
                    "runtime_paths": ["example.js"],
                }
            )
        )

    monkeypatch.setattr(distribution, "prepare", prepare)

    def producer(installation):
        return json.loads((installation / "leaf-distribution.json").read_text())[
            "producer"
        ]

    clean = distribution.cached_installation(tmp_path)
    assert producer(clean)["dirty"] is False
    authored.write_text("<p>Revised draft</p>")
    dirty = distribution.cached_installation(tmp_path)
    assert dirty != clean
    assert producer(dirty)["dirty"] is True
    assert len(preparations) == 1
    assert (dirty / "runtime/bundle.js").stat().st_ino == (
        clean / "runtime/bundle.js"
    ).stat().st_ino
    git("add", ".")
    git("commit", "-m", "Revised authored page")
    committed = distribution.cached_installation(tmp_path)
    assert producer(committed)["commit"] != producer(clean)["commit"]
    assert producer(committed)["dirty"] is False
    assert len(preparations) == 1
    assert producer(clean)["dirty"] is False
    assert producer(dirty)["dirty"] is True
    module.write_text("export const example = 2;")
    changed = distribution.cached_installation(tmp_path)
    assert len(preparations) == 2
    assert (changed / "runtime/bundle.js").read_bytes() == module.read_bytes()


def test_identical_extracted_arms_share_the_compiled_content_identity(tmp_path):
    """A comparison's temporary checkout address is not a compiler input."""
    arms = [tmp_path / name for name in ("first", "second")]
    for arm in arms:
        module = arm / "skills/leaf/assets/runtime/example.js"
        module.parent.mkdir(parents=True)
        module.write_text("export const example = 1;")
    assert distribution.installation_identity(
        arms[0]
    ) == distribution.installation_identity(arms[1])
