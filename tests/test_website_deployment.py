"""Deployment contracts that Wrangler's account-blind dry run cannot prove."""

from pathlib import Path

import tomllib

ROOT = Path(__file__).parent.parent


def test_container_keeps_its_deployed_application_identity():
    """A code rename must keep addressing the standing Cloudflare application."""
    config = tomllib.loads((ROOT / "worker" / "wrangler.toml").read_text())
    [container] = config["containers"]
    [binding] = config["durable_objects"]["bindings"]
    [created_class] = config["migrations"][0]["new_sqlite_classes"]
    deployed_name = f"{config['name']}-{created_class.lower()}"

    assert container["name"] == deployed_name
    assert binding["class_name"] == container["class_name"]
