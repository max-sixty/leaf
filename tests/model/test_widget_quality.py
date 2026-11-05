"""Widget quality examples and their data contracts."""

from known_widget_findings import KNOWN, PACKAGES


def test_every_known_finding_names_a_bundled_package():
    """An entry under a package that is gone is never compared, so never deleted."""
    assert set(KNOWN) <= {package.name for package in PACKAGES}


def test_example_data_validates_bound_sources():
    import pytest

    from leaf.registry.contract import RegistryError
    from leaf.validation.composition import validate_registry_examples

    registry: dict[str, dict] = {
        "$data": {
            "contracts": {
                "rows": {"schema": {"type": "array", "items": {"type": "string"}}}
            }
        },
        "lf-feed": {
            "type": "object",
            "properties": {"id": {"type": "string"}, "source": {"type": "string"}},
            "x-content": "empty",
            "x-data": {
                "rows": {"source": "source", "contract": "rows", "property": "value"}
            },
            "x-example": '<lf-feed id="feed" source="rows"></lf-feed>',
            "x-example-data": {"rows": ["One"]},
        },
    }
    assert validate_registry_examples(registry, "feed") is registry
    registry["lf-feed"]["x-example-data"] = {"rows": [42]}
    with pytest.raises(RegistryError, match="invalid for contract"):
        validate_registry_examples(registry, "feed")
    registry["lf-feed"]["x-example-data"] = {"typo": []}
    with pytest.raises(RegistryError, match="not bound in x-example"):
        validate_registry_examples(registry, "feed")


def test_examples_reusing_sources_keep_independent_values():
    from leaf.render_gate.widget_quality import example_pages

    registry: dict[str, dict] = {
        name: {
            "x-data": {"rows": {"source": "source", "contract": "rows"}},
            "x-example": f'<{name} id="{name}" source="rows"></{name}>',
            **({"x-example-data": {"rows": ["One"]}} if name == "lf-one" else {}),
        }
        for name in ("lf-one", "lf-two")
    }
    pages = example_pages(registry, list(registry))
    assert [(layout, data) for layout, _, data in pages] == [
        ("column", {"rows": ["One"]}),
        ("workspace", {"rows": ["One"]}),
        ("column", {}),
        ("workspace", {}),
    ]
