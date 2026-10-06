"""Pytest collect-only plugin recording source and real fixture/parameter identities.

Load with -p leaf_dev.test_select.collect in the candidate pytest environment. Supply
--jev-evidence-manifest=FILE and --collect-only; no tests or fixture setup run.
Only ordinary serializable values and paths are retained, never arbitrary repr.
"""

import inspect
import json
import subprocess
from dataclasses import fields, is_dataclass
from pathlib import Path

import pytest

INVENTORY = pytest.StashKey[dict]()


def pytest_addoption(parser):
    parser.addoption(
        "--jev-evidence-manifest", help="Write collected test metadata JSON"
    )


def serialize(value, root):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        try:
            return {"path": value.resolve().relative_to(root).as_posix()}
        except ValueError:
            return {"external_path": str(value)}
    if isinstance(value, (list, tuple)):
        return [serialize(x, root) for x in value]
    if isinstance(value, dict):
        return {str(k): serialize(v, root) for k, v in value.items()}
    if is_dataclass(value) and not isinstance(value, type):
        return {
            "type": type(value).__qualname__,
            "fields": {
                field.name: serialize(getattr(value, field.name), root)
                for field in fields(value)
            },
        }
    return {"type": type(value).__qualname__}


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_collection_modifyitems(config, items):
    """A complete inventory cannot silently lose items to selection hooks."""
    initial = {item.nodeid for item in items}
    yield
    final = {item.nodeid for item in items}
    if initial != final or len(final) != len(items):
        raise pytest.UsageError(
            "Test selection requires complete, unfiltered collection"
        )
    config.stash[INVENTORY] = {
        "complete": True,
        "initial_nodes": len(initial),
        "final_nodes": len(final),
    }


def pytest_collection_finish(session):
    destination = session.config.getoption("--jev-evidence-manifest")
    if not destination:
        return
    root = Path(session.config.rootpath).resolve()
    tracked = set(
        subprocess.check_output(
            ["git", "-C", str(root), "ls-files"], text=True
        ).splitlines()
    )
    items = []
    for item in session.items:
        obj = inspect.unwrap(item.obj)
        lines, line = inspect.getsourcelines(obj)
        source = Path(inspect.getsourcefile(obj)).resolve().relative_to(root).as_posix()
        fixturedefs = []
        for name in item.fixturenames:
            # Pytest selects the most specific definition. A fixture that asks
            # for its own name delegates to the next definition in that chain.
            definitions = item._fixtureinfo.name2fixturedefs.get(name, ())
            active = []
            for fixture in reversed(definitions):
                active.append(fixture)
                if name not in fixture.argnames:
                    break
            for fixture in active:
                obj_fixture = inspect.unwrap(fixture.func)
                filename = inspect.getsourcefile(obj_fixture)
                if filename:
                    filepath = Path(filename).resolve()
                    try:
                        path = filepath.relative_to(root).as_posix()
                    except ValueError:
                        continue
                    if path not in tracked:
                        continue
                    fixture_lines, fixture_line = inspect.getsourcelines(obj_fixture)
                    fixturedefs.append(
                        {
                            "name": name,
                            "function": obj_fixture.__name__,
                            "qualname": obj_fixture.__qualname__,
                            "path": path,
                            "line": fixture_line,
                            "endLine": fixture_line + len(fixture_lines) - 1,
                        }
                    )
        items.append(
            {
                "file": source,
                "nodeid": item.nodeid,
                "function": obj.__name__,
                "qualname": obj.__qualname__,
                "line": line,
                "endLine": line + len(lines) - 1,
                "titlePath": [item.name],
                "fixturenames": list(item.fixturenames),
                "fixturedefs": fixturedefs,
                "params": serialize(item.callspec.params, root)
                if hasattr(item, "callspec")
                else {},
                "nightly": item.get_closest_marker("nightly") is not None,
            }
        )
    destination = Path(destination)
    destination.write_text(json.dumps(items, indent=2) + "\n")
    destination.with_name("collection-summary.json").write_text(
        json.dumps(session.config.stash[INVENTORY], indent=2) + "\n"
    )


def pytest_configure(config):
    """Collect ordinary and nightly identities without executing either group."""
    if hasattr(config.option, "run_nightly"):
        config.option.run_nightly = True
