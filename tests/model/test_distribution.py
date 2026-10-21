"""The runtime a Leaf serves, and package admission, preserve the public kernel
boundary."""

import shutil
import subprocess

import pytest
from leaf import layer as layer_model
from leaf import runtime_selection
from leaf.refusals import Refused
from leaf.revision_artifact import Resource
from leaf_dev import ROOT


def test_a_leaf_serves_the_kernel_only_while_it_matches_the_tree(tmp_path, monkeypatch):
    """A Leaf runs pages under the committed kernel built from the tree's own modules,
    and the source modules once any of them changes, until the kernel is rebuilt. A
    page's vendored layer holds none of it."""
    assets, kernel = tmp_path / "assets", tmp_path / "kernel"
    shutil.copytree(layer_model.ASSETS, assets)
    subprocess.run(
        ["node", ROOT / "build/runtime-bundle.mjs", assets, kernel],
        cwd=ROOT,
        check=True,
    )
    monkeypatch.setattr(runtime_selection, "ASSETS", assets)
    monkeypatch.setattr(runtime_selection, "KERNEL", kernel)

    composition = layer_model.compose_layer(
        layer_model.checked_layer_inputs(layer_model.layer_inputs())
    )
    assert "leaf.js" not in composition.top_files
    assert composition.directory_files["runtime"] == {}
    assert "browser-runtime.js" not in composition.directory_files["vendor"]

    runtime = runtime_selection.read_runtime()
    files = runtime.resources({})
    assert files["/leaf.js"].data == (kernel / "leaf.js").read_bytes()
    assert "/runtime/context.js" not in files
    assert any(path.startswith("/runtime/bundle-") for path in files)
    assert "/vendor/browser-runtime.js" not in files
    assert "/vendor/lit.js" in files

    # A package adds runtime modules beside the runtime's own and may replace a vendor
    # module, but not a runtime module, whatever an older layer captured.
    own = Resource(b"export const own = 1;\n", "application/javascript")
    files = runtime.resources(
        {"/vendor/lit.js": own, "/runtime/helper.js": own, "/runtime/media.js": own}
    )
    assert files["/vendor/lit.js"] is own
    assert files["/runtime/helper.js"] is own
    assert files["/runtime/media.js"] is not own
    assert files["/leaf.js"].data == (kernel / "leaf.js").read_bytes()
    # One that replaces a vendor module the kernel compiled in runs the source
    # modules, so its replacement is the one they load.
    files = runtime.resources({"/vendor/browser-runtime.js": own})
    assert files["/leaf.js"].data == (assets / "leaf.js").read_bytes()
    assert files["/vendor/browser-runtime.js"] is own

    module = assets / "runtime/context.js"
    module.write_text(module.read_text() + "\n")
    stale = runtime_selection.read_runtime()
    files = stale.resources({})
    assert files["/leaf.js"].data == (assets / "leaf.js").read_bytes()
    assert files["/runtime/context.js"].data == module.read_bytes()
    assert not any(path.startswith("/runtime/bundle-") for path in files)
    assert "/vendor/browser-runtime.js" in files
    assert stale.identity != runtime.identity


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
