"""Page vendoring and package admission preserve the public kernel boundary."""

import shutil
import subprocess

import pytest
from leaf_dev import ROOT

from leaf import layer as layer_model
from leaf.refusals import Refused


def test_pages_vendor_the_kernel_only_while_it_matches_the_tree(tmp_path, monkeypatch):
    """A page vendors the committed kernel built from the tree's own modules, and the
    source modules once any of them changes, until the kernel is rebuilt."""
    assets, kernel = tmp_path / "assets", tmp_path / "kernel"
    shutil.copytree(layer_model.ASSETS, assets)
    subprocess.run(
        ["node", ROOT / "build/runtime-bundle.mjs", assets, kernel],
        cwd=ROOT,
        check=True,
    )
    monkeypatch.setattr(layer_model, "ASSETS", assets)
    monkeypatch.setattr(layer_model, "KERNEL", kernel)

    def vendored(*packages):
        roots = layer_model.checked_layer_inputs(
            [*layer_model.layer_inputs(), *packages]
        )
        composition = layer_model.compose_layer(roots)
        return composition.top_files["leaf.js"], composition.directory_files

    entry, files = vendored()
    assert entry == (kernel / "leaf.js").read_bytes()
    assert "context.js" not in files["runtime"]
    assert any(name.startswith("bundle-") for name in files["runtime"])
    assert "browser-runtime.js" not in files["vendor"]
    assert (
        files["runtime"]["layer-generation.js"]
        == (assets / "runtime/layer-generation.js").read_bytes()
    )

    # A package that replaces a vendor module the kernel compiled in loads its own.
    package = tmp_path / "package"
    (package / "vendor").mkdir(parents=True)
    (package / "vendor/browser-runtime.js").write_text("export const own = 1;\n")
    entry, files = vendored(package)
    assert entry == (assets / "leaf.js").read_bytes()
    assert files["vendor"]["browser-runtime.js"] == b"export const own = 1;\n"

    module = assets / "runtime/context.js"
    module.write_text(module.read_text() + "\n")
    entry, files = vendored()
    assert entry == (assets / "leaf.js").read_bytes()
    assert files["runtime"]["context.js"] == module.read_bytes()
    assert not any(name.startswith("bundle-") for name in files["runtime"])
    assert "browser-runtime.js" in files["vendor"]


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
