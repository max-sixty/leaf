"""Complete immutable inputs of one authored revision.

Logical resource URLs are rooted at the page (``/page/app.js``,
``/runtime/widget-api.js``). Page imports use literal, unescaped URL strings;
Tree-sitter reads JavaScript and tinycss2 reads CSS. Only the declared public
layer entry points may cross from authored code into the layer. Capturing the
selected layer whole also preserves its declaration-driven dynamic imports.

A bundle contains exact source bytes, resources, their dependency edges, MIME
types, the effective registry, and implementation provenance. Its canonical
manifest determines its digest. The HTML revision file is the commit marker:
the complete bundle is made durable before that file appears. Readers never
discover a staged or incomplete revision, including after a process crash.
"""

import hashlib
import json
import os
import posixpath
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from urllib.parse import unquote, urlsplit

import tinycss2
import tree_sitter_javascript
from tree_sitter import Language, Parser

from leaf.files import file_stamp, fsync_parents, list_revisions, revision_path
from leaf.schema import BROWSER_DIRS, CONTENT_TYPES, SERVED_PATH, VENDORED_FILES
from leaf.structure import SourceDocument, links_with_rel

PUBLIC_MODULES = ("/runtime/widget-api.js",)
RESOURCE_TYPES = {
    **CONTENT_TYPES,
    ".mjs": "application/javascript",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
}
_JAVASCRIPT = Language(tree_sitter_javascript.language())


class ArtifactError(ValueError):
    """A candidate cannot be captured as a complete local revision."""


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _json(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _read(path: Path) -> bytes:
    return _read_stamped(path, file_stamp(path))


@lru_cache(maxsize=512)
def _read_stamped(path: Path, stamp: tuple | None) -> bytes:
    """Cache stable payload reads without retaining every page ever inspected."""
    return path.read_bytes()


@dataclass(frozen=True)
class Resource:
    data: bytes
    mime: str
    dependencies: tuple[str, ...] = ()

    @property
    def digest(self) -> str:
        return _digest(self.data)


@dataclass(frozen=True)
class RevisionArtifact:
    html: bytes
    resources: Mapping[str, Resource]
    manifest: bytes

    @property
    def digest(self) -> str:
        return _digest(self.manifest)

    @property
    def registry(self) -> dict:
        return json.loads(self.resources["/registry.json"].data)

    @property
    def implementations(self) -> dict:
        return json.loads(self.manifest)["implementations"]


def resolve_dependency(specifier: str, importer: str, *, module=False) -> str:
    """Resolve an authored URL without giving it a filesystem or network escape."""
    where = f"{importer}: {specifier!r}"
    try:
        parsed = urlsplit(specifier)
    except ValueError as error:
        raise ArtifactError(f"{where}: invalid dependency URL: {error}") from error
    if (
        not specifier
        or parsed.scheme
        or parsed.netloc
        or parsed.query
        or (module and parsed.fragment)
        or "\\" in specifier
        or any(ord(char) < 33 for char in specifier)
    ):
        raise ArtifactError(f"{where}: dependency must be a local URL without a query")
    path = unquote(parsed.path)
    if unquote(path) != path or "\\" in path or any(ord(char) < 33 for char in path):
        raise ArtifactError(f"{where}: encoded dependency path is not allowed")
    if module and not path.startswith(("/", "./", "../")):
        raise ArtifactError(
            f"{where}: a module import must name a relative or /page/ URL"
        )
    if not path:
        return importer  # a CSS fragment refers to this document
    if path.startswith("/"):
        resolved = posixpath.normpath(path)
    else:
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(importer), path))
    if resolved.startswith("//") or not resolved.startswith("/"):
        raise ArtifactError(f"{where}: dependency escapes the page")
    if module:
        if not resolved.startswith("/page/") and resolved not in PUBLIC_MODULES:
            raise ArtifactError(
                f"{where}: module imports may use /page/ or a public layer entry point"
            )
        if Path(resolved).suffix not in {".js", ".mjs"}:
            raise ArtifactError(
                f"{where}: a module dependency must have JavaScript MIME type"
            )
    elif not resolved.startswith(("/page/", "/media/")):
        raise ArtifactError(f"{where}: dependency escapes /page/ and /media/")
    return resolved


def _javascript_imports(
    data: bytes,
    path: str,
    *,
    allow_import_attributes: bool = False,
    allow_computed_imports: bool = False,
):
    """Yield exact string-literal spans of static exports/imports and import()."""
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ArtifactError(f"{path}: JavaScript is not UTF-8") from error
    tree = Parser(_JAVASCRIPT).parse(data)
    if tree.root_node.has_error:
        pending = [tree.root_node]
        while pending:
            node = pending.pop()
            if node.is_error or node.is_missing:
                raise ArtifactError(
                    f"{path}:{node.start_point.row + 1}: invalid JavaScript"
                )
            pending.extend(reversed(node.children))
        raise ArtifactError(f"{path}: invalid JavaScript")
    pending = [tree.root_node]
    while pending:
        node = pending.pop()
        if node.type.startswith("jsx_"):
            raise ArtifactError(
                f"{path}:{node.start_point.row + 1}: JSX is not executable JavaScript"
            )
        literal = None
        if node.type in {"import_statement", "export_statement"}:
            literal = node.child_by_field_name("source")
            if not allow_import_attributes and any(
                child.type == "import_attribute" for child in node.named_children
            ):
                raise ArtifactError(
                    f"{path}:{node.start_point.row + 1}: import attributes are not supported for JavaScript modules"
                )
        elif node.type == "call_expression":
            function = node.child_by_field_name("function")
            if function.type == "import":
                arguments = node.child_by_field_name("arguments").named_children
                if len(arguments) != 1 or arguments[0].type != "string":
                    if not allow_computed_imports:
                        raise ArtifactError(
                            f"{path}:{node.start_point.row + 1}: import() requires a literal local module URL"
                        )
                else:
                    literal = arguments[0]
        if literal is not None:
            if any(child.type != "string_fragment" for child in literal.named_children):
                raise ArtifactError(
                    f"{path}:{literal.start_point.row + 1}: module URLs must be unescaped string literals"
                )
            yield (
                literal.start_byte,
                literal.end_byte,
                data[literal.start_byte + 1 : literal.end_byte - 1].decode("utf-8"),
            )
        pending.extend(reversed(node.named_children))


def _css_urls(tokens):
    """Read URLs from CSS syntax, including @import's string form."""
    for token in tokens:
        if token.type == "error":
            raise ArtifactError(f"invalid CSS: {token.message}")
        if token.type == "url":
            yield token.value
        elif token.type == "function" and token.lower_name == "url":
            values = [
                item
                for item in token.arguments
                if item.type not in {"whitespace", "comment"}
            ]
            if len(values) != 1 or values[0].type != "string":
                raise ArtifactError("CSS url() requires one literal URL")
            yield values[0].value
        elif token.type == "at-rule" and token.lower_at_keyword == "import":
            values = [
                item
                for item in token.prelude
                if item.type not in {"whitespace", "comment"}
            ]
            if values and values[0].type == "string":
                if Path(urlsplit(values[0].value).path).suffix != ".css":
                    raise ArtifactError(
                        "CSS @import requires a stylesheet with CSS MIME type"
                    )
                yield values[0].value
            else:
                imported = list(_css_urls(token.prelude))
                if not imported or Path(urlsplit(imported[0]).path).suffix != ".css":
                    raise ArtifactError(
                        "CSS @import requires a stylesheet with CSS MIME type"
                    )
        for attribute in ("prelude", "content", "arguments", "value"):
            nested = getattr(token, attribute, None)
            if isinstance(nested, list):
                yield from _css_urls(nested)


@lru_cache(maxsize=512)
def _css_dependencies(source: str, declarations: bool = False) -> tuple[str, ...]:
    parse = (
        tinycss2.parse_declaration_list if declarations else tinycss2.parse_stylesheet
    )
    return tuple(_css_urls(parse(source)))


def capture_artifact(
    page_dir: Path,
    document: SourceDocument,
    registry: dict,
    *,
    declaration_sources: Mapping[str, str] | None = None,
    widget_sources: Mapping[str, str] | None = None,
) -> RevisionArtifact:
    """Capture the candidate's complete inputs without executing authored code."""
    resources = {}

    def capture(path: str):
        if path in resources:
            return
        source = page_dir / path.removeprefix("/")
        root = page_dir / ("page" if path.startswith("/page/") else "media")
        if path.startswith(("/page/", "/media/")) and (
            not root.resolve().is_relative_to(page_dir.resolve())
            or not source.resolve().is_relative_to(root.resolve())
        ):
            raise ArtifactError(
                f"{path}: dependency escapes its source directory through a symlink"
            )
        try:
            data = _read(source)
        except OSError as error:
            raise ArtifactError(
                f"{path}: cannot capture dependency: {error.strerror}"
            ) from error
        mime = RESOURCE_TYPES.get(
            source.suffix,
            "application/octet-stream"
            if not path.startswith(("/page/", "/media/"))
            else None,
        )
        if mime is None or mime == "text/html":
            raise ArtifactError(f"{path}: unsupported dependency MIME type")
        resources[path] = Resource(data, mime)
        edges = []
        if mime == "application/javascript" and path.startswith("/page/"):
            for _, _, specifier in _javascript_imports(data, path):
                edges.append(resolve_dependency(specifier, path, module=True))
        elif mime == "text/css" and path.startswith("/page/"):
            try:
                css = data.decode("utf-8")
            except UnicodeDecodeError as error:
                raise ArtifactError(f"{path}: CSS is not UTF-8") from error
            for specifier in _css_dependencies(css):
                if specifier.startswith(("#", "data:")):
                    continue
                edges.append(resolve_dependency(specifier, path))
        resources[path] = Resource(data, mime, tuple(sorted(set(edges))))
        for edge in edges:
            capture(edge)

    # The layer's own imports are trusted and include computed widget module URLs.
    # Preserve the complete selected payload rather than infer that dynamic graph.
    for name in VENDORED_FILES:
        if (page_dir / name).is_file():
            capture("/" + name)
    for directory in BROWSER_DIRS:
        for path in sorted((page_dir / directory).rglob("*")):
            if path.is_file() and SERVED_PATH.fullmatch(
                "/" + path.relative_to(page_dir).as_posix()
            ):
                capture("/" + path.relative_to(page_dir).as_posix())
    resources["/registry.json"] = Resource(_json(registry), "application/json")

    if widget_sources is None:
        widget_sources = {
            tag: f"widgets/{tag}.js"
            for tag, entry in registry.items()
            if tag.startswith("lf-")
            and entry.get("x-upgrade")
            and f"/widgets/{tag}.js" in resources
        }
    for source in widget_sources.values():
        capture("/" + source.lstrip("/"))

    entries = []
    for script in document.inline_scripts:
        for _, _, specifier in _javascript_imports(
            script["body"].encode("utf-8"), "/index.html"
        ):
            entries.append(resolve_dependency(specifier, "/index.html", module=True))
    for script in document.external_scripts:
        path = resolve_dependency(script["attrs"]["src"], "/index.html", module=True)
        if not path.startswith("/page/"):
            raise ArtifactError(f"{path}: authored module sources must be under /page/")
        entries.append(path)
    for link in links_with_rel(document.links, "stylesheet"):
        path = resolve_dependency(link["attrs"].get("href", ""), "/index.html")
        if Path(path).suffix != ".css":
            raise ArtifactError(
                f"{path}: a stylesheet dependency must have CSS MIME type"
            )
        entries.append(path)
    for specifier in _css_dependencies(document.css):
        if not specifier.startswith(("#", "data:")):
            entries.append(resolve_dependency(specifier, "/index.html"))
    for style in document.inline_styles:
        for specifier in _css_dependencies(style, declarations=True):
            if not specifier.startswith(("#", "data:")):
                entries.append(resolve_dependency(specifier, "/index.html"))
    entries.extend(document.media_refs)
    entries.extend(
        resolve_dependency(specifier, "/index.html")
        for specifier in document.page_resource_refs
    )
    for entry in entries:
        capture(entry)

    implementations = {
        tag: {
            "path": "/" + source.lstrip("/"),
            "owner": "page" if source.startswith("page/") else "layer",
            "digest": resources["/" + source.lstrip("/")].digest,
        }
        for tag, source in widget_sources.items()
    }
    manifest = _json(
        {
            "html": _digest(document.data),
            "entries": sorted(set(entries)),
            "public_modules": list(PUBLIC_MODULES),
            "layer": registry.get("$layer", {}),
            "declarations": dict(declaration_sources or {}),
            "implementations": implementations,
            "resources": {
                path: {
                    "digest": resource.digest,
                    "mime": resource.mime,
                    "dependencies": list(resource.dependencies),
                }
                for path, resource in sorted(resources.items())
            },
        }
    )
    return RevisionArtifact(document.data, MappingProxyType(resources), manifest)


def artifact_name(revision: int, artifact: RevisionArtifact) -> str:
    return f"r{revision}-{artifact.digest.removeprefix('sha256:')[:16]}"


def write_artifact(page_dir: Path, revision: int, artifact: RevisionArtifact) -> Path:
    """Publish a complete immutable bundle, then its discoverable HTML marker."""
    revisions = page_dir / "revisions"
    revisions.mkdir(exist_ok=True)
    if revision in list_revisions(page_dir):
        raise ArtifactError(f"revision r{revision} already exists")
    name = artifact_name(revision, artifact)
    destination = revisions / name
    marker = revisions / f"{name}.html"
    if not destination.exists():
        with tempfile.TemporaryDirectory(
            prefix=".capture-", dir=revisions
        ) as temporary:
            staged = Path(temporary) / name
            staged.mkdir()
            contents = {"index.html": artifact.html, "manifest.json": artifact.manifest}
            contents.update(
                {
                    "resources" + path: resource.data
                    for path, resource in artifact.resources.items()
                }
            )
            written = []
            for relative, data in contents.items():
                target = staged / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                written.append(target)
            fsync_parents(written + list(staged.rglob("*")))
            os.rename(staged, destination)
            fsync_parents([destination])
    elif (destination / "manifest.json").read_bytes() != artifact.manifest:
        raise ArtifactError(f"{destination}: immutable artifact digest collision")
    os.link(destination / "index.html", marker)
    fsync_parents([marker])
    return marker


def read_artifact(page_dir: Path, revision: int) -> RevisionArtifact:
    """Read exact captured inputs, never substituting a mutable page file."""
    path = revision_path(page_dir, revision)
    bundle = path.with_suffix("")
    manifest_bytes = _read(bundle / "manifest.json")
    manifest = json.loads(manifest_bytes)
    resources = {
        logical: Resource(
            _read(bundle / ("resources" + logical)),
            record["mime"],
            tuple(record["dependencies"]),
        )
        for logical, record in manifest["resources"].items()
    }
    return RevisionArtifact(_read(path), MappingProxyType(resources), manifest_bytes)


def rewrite_module(data: bytes, logical_path: str, prefix: str) -> bytes:
    """Bind authored literal imports to the same revision's HTTP resource prefix."""
    for start, end, specifier in reversed(
        list(_javascript_imports(data, logical_path))
    ):
        target = resolve_dependency(specifier, logical_path, module=True)
        data = data[:start] + _json(prefix.rstrip("/") + target) + data[end:]
    return data


def rewrite_captured_module(
    data: bytes,
    logical_path: str,
    prefix: str,
    resources: Mapping[str, Resource],
) -> bytes:
    """Bind one trusted captured layer module to an offline resource namespace.

    Page modules continue through :func:`rewrite_module`, whose public-import boundary
    is intentionally narrower. The vendored layer is already the captured trusted
    graph; this pass only gives its literal imports addresses that remain usable from
    ``data:`` modules. Its one computed door is widget loading, which the runtime binds
    from the captured registry at execution time.
    """
    if logical_path.startswith("/page/"):
        return rewrite_module(data, logical_path, prefix)
    for start, end, specifier in reversed(
        list(
            _javascript_imports(
                data,
                logical_path,
                allow_import_attributes=True,
                allow_computed_imports=True,
            )
        )
    ):
        parsed = urlsplit(specifier)
        if (
            not specifier
            or parsed.scheme
            or parsed.netloc
            or parsed.query
            or parsed.fragment
            or "\\" in specifier
            or any(ord(char) < 33 for char in specifier)
        ):
            raise ArtifactError(
                f"{logical_path}: {specifier!r}: captured layer import is not local"
            )
        target = posixpath.normpath(
            parsed.path
            if parsed.path.startswith("/")
            else posixpath.join(posixpath.dirname(logical_path), parsed.path)
        )
        if not target.startswith("/") or target not in resources:
            raise ArtifactError(
                f"{logical_path}: {specifier!r}: captured layer import is missing"
            )
        data = data[:start] + _json(prefix.rstrip("/") + target) + data[end:]
    return data
