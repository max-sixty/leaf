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
it and any runtime change moves it. A served document and every answer name it, so a
tab from before a restart under another runtime refuses the answer and reloads rather
than reading a newer server's state with older code (`runtime/transport/layer-client.js`).

An execution's identity (`executing`) covers every byte a page server answers under
the address it gives the execution's resources (`http.assets_path`): the runtime, the
composed layer and vocabulary, and the files the revision captured, apart from media,
which answers at the page root. So a cached address never names other bytes. The identity covers nothing of the document itself,
so the revisions an agent saves as it edits a page's prose share one address, and a
reload after one of them fetches none of the runtime again.

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

from leaf.base.schema import (
    ASSETS,
    BROWSER_DIRS,
    KERNEL,
    KERNEL_FILES,
    MEDIA_DIR,
    PACKAGE_FILES,
    RUNTIME_DIRS,
    RUNTIME_ENTRY,
)
from leaf.base.state import PLUGIN_ROOT, json_bytes
from leaf.source.layer import (
    LayerComposition,
    composed_sheets,
    files_identity,
    forget_layers,
    layer_inputs,
    package_files,
    selected_layer,
    stylesheet,
)
from leaf.source.render_checks import PROBE_SOURCES
from leaf.source.revision_artifact import (
    PAGE_DECLARATIONS,
    Resource,
    RevisionArtifact,
    resource_type,
    revision_vocabulary,
)

# Non-CSS core inputs. Core stylesheet identity comes
# from the same composition that delivers them, including its imports and roles.
LAYER_SOURCES = (
    *(f"browser/{name}" for name in KERNEL_FILES if not name.endswith(".css")),
    "browser/widgets",
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
        """Names every runtime input and browser layer contribution this tree holds, so a
        change to a bundled widget, like one to the runtime, gives an open document
        a server that refuses it. Package scripts, their generated files and author
        instructions do not change the browser's runtime."""
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
                **{
                    f"layer:/packages/{package.name}{path}": data
                    for package in sorted((PLUGIN_ROOT / "packages").glob("*"))
                    if package.is_dir()
                    for path, data in _files(
                        package, *PACKAGE_FILES, *BROWSER_DIRS
                    ).items()
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
        # A prepared installation's build records the SHA-256 of each file it read:
        # `leaf.js`, each `.js` under the kernel's browser directories, and each file
        # it compiled in as values, such as the kernel registry
        # (`build/runtime-bundle.mjs`, `kernelOutputs`). A tree whose files differ
        # runs its source modules, so an install never runs a runtime other than the
        # one its tree holds.
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


def forget_tree() -> None:
    """Drop what this process holds of its tree, the runtime it serves and the layers
    it composed (`layer.forget_layers`), so the next server it starts reads the tree as
    it stands. Only a process between servers drops them, as a preview does when it
    replaces its own: a server still running would answer with bytes it did not start
    with."""
    serving_runtime.cache_clear()
    forget_layers()


def execution_identity(artifact: RevisionArtifact) -> str:
    """The identity of every byte the artifact's execution serves (`executing`)."""
    return executing(artifact).identity


def named_execution(
    artifact: RevisionArtifact, identity: str
) -> _ExecutingArtifact | None:
    """The execution of `artifact` an address names by `identity`, or None where
    this process runs it under no such identity.

    An address names the same bytes for as long as a browser may cache it, so the
    execution a document was served under answers the few hundred resource requests
    its load makes without `executing` reading the page's package copies again for
    each; the next document load is where a replaced copy shows."""
    held = serving_runtime()._executed.get(artifact)
    if held is not None and held[1].identity == identity:
        return held[1]
    executed = executing(artifact)
    return executed if executed.identity == identity else None


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
    manifest = json.loads(artifact.manifest)
    record = manifest["layer"]
    composition = selected_layer(record, artifact.page_dir)
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
        manifest,
        declarations.data if declarations is not None else None,
        artifact.page_dir,
        layer=composition.vocabulary,
    )
    layer["/registry.json"] = Resource(json_bytes(registry), "application/json")
    # Agent instructions belong to the composition's fingerprint, but only the
    # browser's bytes belong to its immutable resource address: the layer's files,
    # digested once for every revision that selects the layer, and this revision's
    # vocabulary. The revision's captured files are served at the same address, so
    # the identity covers each by the digest its manifest records, and covers each
    # widget alias, whose module names its implementation at that address. Media
    # answers at the page root under a name that is its own digest, never at this
    # address, so the identity leaves it out and a revision that adds an image keeps
    # the address.
    identity = files_identity(
        {
            "runtime": runtime.identity.encode(),
            "layer": composition.files_digest.encode(),
            "/registry.json": layer["/registry.json"].data,
            **{
                f"capture:{path}": captured["digest"].encode()
                for path, captured in manifest["resources"].items()
                if not path.startswith(f"/{MEDIA_DIR}/")
            },
            **{
                f"alias:{alias}": source.encode()
                for alias, source in artifact.widget_aliases.items()
                if alias != source
            },
        }
    ).removeprefix("sha256:")[:16]
    # Samples re-compose in their own directory. Keep just the local package
    # copies this selection needs, using the same file inventory as page init.
    names = tuple(record["packages"])
    copies = {
        root.relative_to(artifact.page_dir).as_posix(): MappingProxyType(
            package_files(root)
        )
        for root in layer_inputs(names, artifact.page_dir)
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
