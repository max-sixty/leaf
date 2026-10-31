"""The browser runtime and layer a page's documents execute: the serving Leaf's own.

A revision captures what its author owns — the document, its modules and media, and
its own declarations (`revision_artifact`). Everything else comes from the Leaf
serving, checking or exporting the page: `leaf.js`, `runtime/`, the kernel's
`vendor/` modules and the render-check probes, and the layer composed from the
packages the revision selects (`layer.selected_layer`), its registry, theme,
widgets and package modules. So neither the state a server serves nor the widgets
it draws with cross a version gap. What still crosses one, the event log and the
records kept outside a page, is the page protocol's (`layer-registry.md`, "Page
protocol"). A historical revision therefore runs under the current runtime and
layer: its authored content and recorded decisions remain available independently
of the renderer that drew them.

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
layer's `/vendor/` file wins over the runtime's. Where it replaces a module compiled
into the kernel, the revision runs the source modules instead, since the kernel holds
its own copy: the kernel is chosen only while it was compiled from the modules this
tree holds and no layer file replaces one it compiled in.
"""

import hashlib
import json
import weakref
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import cache, cached_property
from types import MappingProxyType

from .layer import (
    LayerComposition,
    composed_sheets,
    files_identity,
    layer_inputs,
    stylesheet,
)
from .registry.storage import revision_vocabulary, selected
from .render_checks import PROBE_SOURCES
from .revision_artifact import (
    PAGE_DECLARATIONS,
    Resource,
    RevisionArtifact,
    resource_type,
)
from .schema import ASSETS, KERNEL, KERNEL_FILES, RUNTIME_DIRS, RUNTIME_ENTRY
from .state import PLUGIN_ROOT, json_bytes
from .themes import theme_package

# Non-CSS core inputs and the bundled packages. Core stylesheet identity comes
# from the same composition that delivers them, including its imports and roles.
LAYER_SOURCES = (
    *(f"browser/{name}" for name in KERNEL_FILES if not name.endswith(".css")),
    "browser/widgets",
    "packages",
)


def _files(root, *names) -> dict[str, bytes]:
    """Every file under `root`'s `names`, by its rooted layer path, each stylesheet as
    a page receives it (`layer.stylesheet`)."""
    found = {}
    for name in names:
        top = root / name
        for path in sorted([top] if top.is_file() else top.rglob("*")):
            if path.is_file():
                found["/" + path.relative_to(root).as_posix()] = (
                    stylesheet(path, root).encode()
                    if path.suffix == ".css"
                    else path.read_bytes()
                )
    return found


@dataclass(frozen=True, eq=False)
class _ExecutingArtifact(RevisionArtifact):
    """One execution's identity and bytes, including its vocabulary and the local
    package sources a child sample needs to compose the same layer."""

    identity: str
    package_copies: Mapping[str, Mapping[str, bytes]]

    @cached_property
    def registry(self) -> dict:
        return json.loads(self.resources["/registry.json"].data)


@dataclass(frozen=True)
class ServingRuntime:
    """One Leaf's browser runtime, read whole: its source modules, the compiled
    kernel where it is current, and the probes."""

    source: Mapping[str, bytes]
    kernel: Mapping[str, bytes] | None
    replaces: frozenset[str]
    probes: Mapping[str, bytes]
    # What `executing` made of each artifact something still holds.
    _executed: weakref.WeakKeyDictionary[
        RevisionArtifact, tuple[LayerComposition, _ExecutingArtifact]
    ] = field(
        default_factory=weakref.WeakKeyDictionary, init=False, repr=False, compare=False
    )

    @cached_property
    def identity(self) -> str:
        """Names every runtime input and every layer input this tree holds, so a
        change to a bundled widget, like one to the runtime, gives an open document
        a server that refuses it."""
        return files_identity(
            {
                **self.source,
                **{
                    f"kernel:{path}": data for path, data in (self.kernel or {}).items()
                },
                **self.probes,
                **{
                    f"layer:/browser/{name}": data
                    for name, data in composed_sheets([ASSETS]).items()
                },
                **{
                    f"layer:{path}": data
                    for path, data in _files(PLUGIN_ROOT, *LAYER_SOURCES).items()
                },
            }
        ).removeprefix("sha256:")[:16]

    @cached_property
    def _variants(self) -> dict[bool, Mapping[str, Resource]]:
        def resources(files: Mapping[str, bytes]) -> Mapping[str, Resource]:
            return MappingProxyType(
                {
                    path: Resource(data, resource_type(path))
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

    def resources(
        self, layer: Mapping[str, Resource], captured: Mapping[str, Resource]
    ) -> Mapping[str, Resource]:
        """What a revision runs over `layer` with what it `captured`: the runtime's
        files, with the layer's `/vendor/` modules that replace one of them, the
        rest of the layer, and every captured file."""
        source = self._variants[False]
        replaced = {
            path for path in layer if path in source and path.startswith("/vendor/")
        }
        runtime = self._variants[
            self.kernel is not None and not replaced & self.replaces
        ]
        return {
            **runtime,
            **{
                path: resource
                for path, resource in layer.items()
                if path not in runtime or path in replaced
            },
            **{
                path: resource
                for path, resource in captured.items()
                if path not in runtime
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


def execution_identity(artifact: RevisionArtifact) -> str:
    """The identity of the same runtime and layer that supplies the artifact's bytes."""
    return executing(artifact).identity


def executing(artifact: RevisionArtifact) -> _ExecutingArtifact:
    """Freeze one execution of `artifact`: its runtime, selected layer, vocabulary
    and resources under one identity. An execution passed back is already frozen.

    A live artifact follows replacement of a page's package copy; the runtime keeps
    its execution while that composition is unchanged. A snapshot holds the returned
    execution itself, so later package replacement changes neither its addresses nor
    the bytes they serve. The authored manifest and digest remain unchanged."""
    if isinstance(artifact, _ExecutingArtifact):
        return artifact
    runtime = serving_runtime()
    record = json.loads(artifact.manifest)["layer"]
    composition = selected(record, artifact.page_dir)
    held = runtime._executed.get(artifact)
    if held is not None and held[0] is composition:
        return held[1]
    layer = {
        path: Resource(data, resource_type(path))
        for path, data in composition.files.items()
    }
    # The original artifact may have cached a vocabulary from an earlier package
    # copy. Read this execution's vocabulary against the selected composition.
    declarations = artifact.resources.get(PAGE_DECLARATIONS)
    registry = revision_vocabulary(
        json.loads(artifact.manifest),
        declarations.data if declarations is not None else None,
        artifact.page_dir,
    )
    layer["/registry.json"] = Resource(json_bytes(registry), "application/json")
    identity = files_identity(
        {
            "runtime": runtime.identity.encode(),
            "layer": composition.fingerprint.encode(),
        }
    ).removeprefix("sha256:")[:16]
    # Samples re-compose in their own directory. Keep just the local package
    # copies this selection needs, using the same file inventory as page init.
    from .vendoring import package_files

    names = [*record["packages"]]
    if theme := theme_package(record["theme"]):
        names.append(theme)
    copies = {
        root.relative_to(artifact.page_dir).as_posix(): MappingProxyType(
            package_files(root)
        )
        for root in layer_inputs(tuple(names), artifact.page_dir)
        if root.is_relative_to(artifact.page_dir)
    }
    executed = _ExecutingArtifact(
        artifact.html,
        MappingProxyType(runtime.resources(layer, artifact.resources)),
        artifact.manifest,
        artifact.page_dir,
        identity,
        MappingProxyType(copies),
    )
    runtime._executed[artifact] = (composition, executed)
    return executed
