"""Developer tooling checks; run explicitly from dev/tests."""

from pathlib import Path

from leaf_dev.commands import distribution


def test_current_kernel_compiles_only_a_stale_kernel_in_place(tmp_path, monkeypatch):
    """A tree whose kernel matches its modules is served as it stands; a stale one
    gets a fresh compile of a snapshot of its modules, so an edit landing meanwhile
    leaves the kernel stale rather than recorded as current, and the compile keeps
    nothing of the kernel it replaces."""
    module = tmp_path / "browser/runtime/example.js"
    module.parent.mkdir(parents=True)
    module.write_text("export const example = 1;")
    kernel = tmp_path / "dist/kernel"
    (kernel / "runtime").mkdir(parents=True)
    (kernel / "runtime/removed.js").write_text("export {};")
    (kernel / "kernel.json").write_text("{}")
    reading = {"current": True}
    monkeypatch.setattr(
        distribution,
        "kernel_reading",
        lambda tree: (Path("browser"), Path("dist/kernel"), reading["current"]),
    )
    built = []

    def bundle(assets, staged):
        module.write_text("export const example = 2;")
        built.append((assets / "runtime/example.js").read_text())
        (staged / "runtime").mkdir(parents=True)
        (staged / "leaf.js").write_text("export {};")
        (staged / "kernel.json").write_text('{"inputs": {}}')

    monkeypatch.setattr(distribution, "bundle_runtime", bundle)
    assert distribution.current_kernel(tmp_path) == tmp_path
    assert built == []
    assert (kernel / "runtime/removed.js").is_file()

    reading["current"] = False
    distribution.current_kernel(tmp_path)
    assert built == ["export const example = 1;"]
    assert sorted(p.relative_to(kernel).as_posix() for p in kernel.rglob("*")) == [
        "kernel.json",
        "leaf.js",
    ]
    assert (kernel / "kernel.json").read_text() == '{"inputs": {}}'
    assert [p.name for p in (tmp_path / "dist").iterdir()] == ["kernel"]
