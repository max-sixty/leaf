"""`leaf-dev`: developer commands loaded only when selected.

Each command's module owns its options and detailed help. Root help lists their
names without loading Leaf, browser tooling, or the website adapter.
"""

from importlib import import_module

import click

COMMANDS = {
    "bench-check": "bench_check",
    "bench-latency": "bench_latency",
    "bugback": "bugback",
    "corpus": "corpus",
    "delivery-eval": "delivery_eval",
    "fetch-assets": "leaf_assets",
    "flake": "flake",
    "guidance-eval": "guidance_eval",
    "keydocs": "keydocs",
    "preview": "preview",
    "probe": "probe",
    "profile": "profile",
    "publish-media": "page_fixtures",
    "record-demo": "record_demo",
    "refresh-previews": "example_previews",
    "site": "site",
    "stills": "stills",
    "verify-codex-task": "verify_codex_task",
    "verify-site": "verify_site",
}


class DeveloperCommands(click.Group):
    def list_commands(self, ctx):
        return sorted(COMMANDS)

    def get_command(self, ctx, cmd_name):
        if cmd_name not in COMMANDS:
            return None
        module = import_module(f"leaf_dev.{COMMANDS[cmd_name]}")
        return getattr(module, cmd_name.replace("-", "_"))

    def format_commands(self, ctx, formatter):
        with formatter.section("Commands"):
            formatter.write_dl((name, "") for name in self.list_commands(ctx))


@click.group(cls=DeveloperCommands)
def cli() -> None:
    """Leaf's developer tooling. Use COMMAND --help for command options."""
