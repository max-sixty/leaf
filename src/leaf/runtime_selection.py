"""The browser runtime a page's documents execute: the serving Leaf's own.

A page directory vendors what its layer's packages and its author own — the registry,
the composed theme, widgets, package modules — and each revision captures those
(`revision_artifact`). The runtime that executes them is not vendored: `leaf.js`,
`runtime/`, the kernel's `vendor/` modules and the render-check probes come from the
Leaf serving, checking or exporting the page, so the state a server serves crosses no
version gap. What still crosses one, the event log, what a page sends, records kept
outside a page, vendored declarations and the public package API, is the page
protocol's (`layer-registry.md`, "Page protocol"). A historical revision therefore
runs under the current runtime: its authored content and recorded decisions remain
available independently of the renderer that drew them.

`serving_runtime` reads the whole runtime once per process, which a page server does
as it binds (`http.page_app`), and holds its bytes rather than its paths: a plugin
update replaces the installed tree under a running server, and a server must keep
answering a document's later imports with the bytes its first ones came from.

`identity` is a digest of every runtime input, so a restart of the same build keeps
it and any runtime change moves it. A host addresses the resources a document runs
with under it (`http.PageEndpoint._document_asset_root`), so an immutable cached
address never names other bytes, and a served document and every answer name it, so a
tab from before a restart under another runtime refuses the answer and reloads rather
than reading a newer server's state with older code (`runtime/layer-client.js`).

A package may add modules beside the runtime's and replace a vendor module of the
kernel's (`layer.compose_layer` refuses one replacing a private runtime module), so a
captured `/vendor/` file wins over the runtime's. Where it replaces a module compiled
into the kernel, the revision runs the source modules instead, since the kernel holds
its own copy: the kernel is chosen only while it was compiled from the modules this
tree holds and no captured file replaces one it compiled in.
"""

import hashlib
import json
import weakref
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from functools import cache, cached_property
from pathlib import PurePosixPath
from types import MappingProxyType

from .layer import files_identity
from .render_checks import PROBE_SOURCES
from .revision_artifact import RESOURCE_TYPES, Resource, RevisionArtifact
from .schema import ASSETS, KERNEL, RUNTIME_DIRS, RUNTIME_ENTRY


def _files(root, *names) -> dict[str, bytes]:
    """Every file under `root`'s `names`, by its rooted layer path."""
    found = {}
    for name in names:
        top = root / name
        for path in sorted([top] if top.is_file() else top.rglob("*")):
            if path.is_file():
                found["/" + path.relative_to(root).as_posix()] = path.read_bytes()
    return found


@dataclass(frozen=True)
class ServingRuntime:
    """One Leaf's browser runtime, read whole: its source modules, the compiled
    kernel where it is current, and the probes."""

    source: Mapping[str, bytes]
    kernel: Mapping[str, bytes] | None
    replaces: frozenset[str]
    probes: Mapping[str, bytes]
    # What `executing` made of each artifact something still holds.
    _executed: weakref.WeakKeyDictionary[RevisionArtifact, RevisionArtifact] = field(
        default_factory=weakref.WeakKeyDictionary, init=False, repr=False, compare=False
    )

    @cached_property
    def identity(self) -> str:
        return files_identity(
            {
                **self.source,
                **{
                    f"kernel:{path}": data for path, data in (self.kernel or {}).items()
                },
                **self.probes,
            }
        ).removeprefix("sha256:")[:16]

    @cached_property
    def _variants(self) -> dict[bool, Mapping[str, Resource]]:
        def resources(files: Mapping[str, bytes]) -> Mapping[str, Resource]:
            return MappingProxyType(
                {
                    path: Resource(
                        data,
                        RESOURCE_TYPES.get(
                            PurePosixPath(path).suffix, "application/octet-stream"
                        ),
                    )
                    for path, data in {**files, **self.probes}.items()
                }
            )

        variants = {False: resources(self.source)}
        if self.kernel is not None:
            kernelled = {
                path: data
                for path, data in self.source.items()
                if path not in self.replaces
            }
            variants[True] = resources({**kernelled, **self.kernel})
        return variants

    def resources(self, captured: Mapping[str, Resource]) -> Mapping[str, Resource]:
        """What a revision that captured `captured` runs: the runtime's files, with
        the captured `/vendor/` modules that replace one of them, and every captured
        file the runtime does not supply."""
        source = self._variants[False]
        replaced = {
            path for path in captured if path in source and path.startswith("/vendor/")
        }
        runtime = self._variants[
            self.kernel is not None and not replaced & self.replaces
        ]
        return {
            **runtime,
            **{
                path: resource
                for path, resource in captured.items()
                if path not in runtime or path in replaced
            },
        }


def read_runtime() -> ServingRuntime:
    """This tree's runtime as it stands on disk now."""
    source = _files(ASSETS, RUNTIME_ENTRY, *RUNTIME_DIRS)
    probes = {logical: path.read_bytes() for logical, path in PROBE_SOURCES.items()}
    kernel = None
    replaces = frozenset()
    record = KERNEL / "kernel.json"
    if record.is_file():
        built = json.loads(record.read_text())
        # The build records the SHA-256 of each file it read: `leaf.js`, each `.js`
        # under the kernel's browser directories, and each file it compiled in as
        # values, such as the kernel registry (`build/runtime-bundle.mjs`,
        # `kernelOutputs`). A tree whose files differ, such as a branch whose runtime or
        # registry edit has not been rebuilt, runs its source modules, so an install
        # never runs a runtime other than the one its tree holds.
        modules = {
            path.lstrip("/"): hashlib.sha256(data).hexdigest()
            for path, data in {**source, **_files(ASSETS, "widgets")}.items()
            if path.endswith(".js") or path.lstrip("/") in built["inputs"]
        }
        if modules == built["inputs"]:
            kernel = _files(KERNEL, "leaf.js", "runtime")
            replaces = frozenset("/" + path for path in built["replaces"])
    return ServingRuntime(
        MappingProxyType(source),
        MappingProxyType(kernel) if kernel is not None else None,
        replaces,
        MappingProxyType(probes),
    )


@cache
def serving_runtime() -> ServingRuntime:
    """The runtime this process serves, read once (`read_runtime`)."""
    return read_runtime()


def executing(artifact: RevisionArtifact) -> RevisionArtifact:
    """`artifact` with the resources its documents run with under this process's
    runtime (`ServingRuntime.resources`). Its captured identity is unchanged: the
    manifest, and with it the digest and executable, describe what the revision
    captured, and the runtime is named beside it by `serving_runtime().identity`.

    The runtime keeps one per artifact for as long as the artifact is kept
    (`revision_artifact.read_artifact`), so what a reader derives from it, such as
    its registry and widget aliases, is read once rather than on each of the few
    dozen resource requests a document makes."""
    runtime = serving_runtime()
    executed = runtime._executed.get(artifact)
    if executed is None:
        executed = runtime._executed[artifact] = replace(
            artifact,
            resources=MappingProxyType(runtime.resources(artifact.resources)),
        )
    return executed
