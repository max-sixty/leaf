"""The runtime a Leaf serves, and package admission, preserve the public kernel
boundary."""

import shutil

import pytest

from leaf import layer as layer_model
from leaf import runtime_selection
from leaf.refusals import Refused
from leaf.revision_artifact import Resource
from leaf_dev.commands.distribution import bundle_runtime


def test_a_leaf_serves_the_kernel_only_while_it_matches_the_tree(tmp_path, monkeypatch):
    """A Leaf runs pages under the committed kernel built from the tree's own modules,
    and the source modules once any of them changes, until the kernel is rebuilt. The
    layer a page selects holds none of it."""
    assets, kernel = tmp_path / "assets", tmp_path / "kernel"
    shutil.copytree(layer_model.ASSETS, assets)
    bundle_runtime(assets, kernel)
    monkeypatch.setattr(runtime_selection, "ASSETS", assets)
    monkeypatch.setattr(runtime_selection, "KERNEL", kernel)

    composition = layer_model.compose_layer(
        layer_model.checked_layer_inputs(layer_model.layer_inputs())
    )
    assert "leaf.js" not in composition.top_files
    assert composition.directory_files["runtime"] == {}
    assert "signals-core.js" not in composition.directory_files["vendor"]

    runtime = runtime_selection.read_runtime()
    files = runtime.resources({}, {})
    assert files["/leaf.js"].data == (kernel / "leaf.js").read_bytes()
    assert "/runtime/context.js" not in files
    assert any(path.startswith("/runtime/bundle-") for path in files)
    assert "/vendor/signals-core.js" not in files
    assert "/vendor/lit.js" in files
    # The kernel holds the kernel registry's facts as values, so it serves no copy.
    assert "/runtime/kernel-registry.json" not in files

    # A package adds runtime modules beside the runtime's own and may replace a vendor
    # module, but not a runtime module, whatever the layer holds.
    own = Resource(b"export const own = 1;\n", "application/javascript")
    files = runtime.resources(
        {"/vendor/lit.js": own, "/runtime/helper.js": own, "/runtime/media.js": own},
        {},
    )
    assert files["/vendor/lit.js"] is own
    assert files["/runtime/helper.js"] is own
    assert files["/runtime/media.js"] is not own
    assert files["/leaf.js"].data == (kernel / "leaf.js").read_bytes()
    # One that replaces a vendor module the kernel compiled in runs the source
    # modules, so its replacement is the one they load.
    files = runtime.resources({"/vendor/signals-core.js": own}, {})
    assert files["/leaf.js"].data == (assets / "leaf.js").read_bytes()
    assert files["/vendor/signals-core.js"] is own

    # A JSON file the kernel never read leaves it current; the kernel registry it
    # compiled in does not, so an edit to it reaches the browser through the source
    # modules, which read it, as it reaches Python.
    unread = assets / "vendor/unread.json"
    unread.write_text("{}\n")
    assert runtime_selection.read_runtime().kernel is not None
    registry = assets / "runtime/kernel-registry.json"
    shipped = registry.read_bytes()
    registry.write_bytes(shipped + b"\n")
    files = runtime_selection.read_runtime().resources({}, {})
    assert files["/leaf.js"].data == (assets / "leaf.js").read_bytes()
    assert files["/runtime/kernel-registry.json"].data == registry.read_bytes()
    registry.write_bytes(shipped)

    module = assets / "runtime/context.js"
    module.write_text(module.read_text() + "\n")
    stale = runtime_selection.read_runtime()
    files = stale.resources({}, {})
    assert files["/leaf.js"].data == (assets / "leaf.js").read_bytes()
    assert files["/runtime/context.js"].data == module.read_bytes()
    assert not any(path.startswith("/runtime/bundle-") for path in files)
    assert "/vendor/signals-core.js" in files
    assert stale.identity != runtime.identity

    # The runtime's sheets are read from their sources, so an edit to a file one
    # imports needs no build to be served.
    imported = assets / "styles/floating-panel.css"
    imported.write_text(imported.read_text() + ".lf-edited { color: red; }\n")
    chrome = runtime_selection.read_runtime().resources({}, {})["/runtime/chrome.css"]
    assert b".lf-edited" in chrome.data
    assert b"@import" not in chrome.data


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
