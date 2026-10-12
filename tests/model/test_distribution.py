"""The website's prepared install needs no compiler, including for custom packages.

Exercise the actual copied launcher, kernel, render probes and offline document.
Compiler shims fail every attempted Node/package-manager invocation after preparation.
"""

import pytest
from leaf.refusals import Refused


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
