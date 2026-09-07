"""Deployment contracts that Wrangler's account-blind dry run cannot prove."""

import tomllib
from pathlib import Path


ROOT = Path(__file__).parent.parent


def test_container_keeps_its_deployed_durable_object_identity():
    """A code rename must not silently ask Cloudflare for a second application."""
    config = tomllib.loads((ROOT / "worker" / "wrangler.toml").read_text())
    [container] = config["containers"]
    [binding] = config["durable_objects"]["bindings"]
    created_classes = {
        class_name
        for migration in config["migrations"]
        for class_name in migration.get("new_sqlite_classes", [])
    }

    assert container["class_name"] in created_classes, (
        "renaming a deployed container class changes its Cloudflare application identity"
    )
    assert binding["class_name"] == container["class_name"]
