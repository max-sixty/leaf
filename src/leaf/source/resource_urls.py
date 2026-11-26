"""The resources authored code names, and each one's browser URL identity, shared by
source readings, layer composition, capture and delivery.

Logical resource URLs are rooted at the page (``/page/app.js``,
``/runtime/widget-api.js``). A module names its imports in literal, unescaped URL
strings, which Tree-sitter reads (`javascript_imports`); a stylesheet's URLs are
`styles.css_dependencies`. Only the declared public layer entry points
(`PUBLIC_MODULES`) may cross from authored code into the layer
(`resolve_dependency`), and an authored module's imports are read through that gate
(`authored_imports`). A reference no revision can hold is refused as a capture
problem (`capture_refusals`), whoever reads it."""

import posixpath
from functools import cache, lru_cache
from pathlib import Path
from urllib.parse import quote, unquote

from pywhatwgurl import URL

from leaf.base.findings import Finding
from leaf.base.schema import JAVASCRIPT_SUFFIXES, kernel_registry
from leaf.source.capture_refusals import ArtifactError, artifact_error, capture_finding


class ReferenceError(ValueError):
    """A URL cannot name a supported resource; admission adds its source location."""

    def __init__(self, code: str, **values):
        self.code = code
        self.values = values
        super().__init__(code)


def resource_reference(
    specifier: str, importer: str, *, module=False
) -> tuple[str, str] | None:
    """A browser URL's decoded filesystem path and its query/fragment suffix.

    The WHATWG parser resolves URL syntax; filesystem normalization and the
    caller's containment gate decide which local file it names. Decoding happens
    once, so escaped percent signs remain literal parts of filenames. A module's
    suffix is refused because the captured module graph keys execution by path.
    Capture has no deployment origin: a resource must be local on both HTTP and
    HTTPS or external on both. Scheme-dependent references are refused rather
    than silently omitting a file the browser can load locally.
    """
    base = "https://leaf.invalid"
    other_base = "http://relative.invalid"
    importer_url = quote(importer, safe="/")
    other_importer_url = importer_url + "-reference"
    try:
        url = URL(specifier, base + importer_url)
    except ValueError as error:
        raise ReferenceError("dependency-url", error=str(error)) from error
    if url.protocol == "data:":
        return None
    if not specifier or url.protocol not in {"http:", "https:"}:
        raise ReferenceError("dependency-not-local")
    # A local reference follows either base's origin. Absolute and network-path
    # references keep their own host, even when it happens to equal one base.
    try:
        other = URL(specifier, other_base + other_importer_url)
    except ValueError as error:
        raise ReferenceError("dependency-scheme-dependent") from error
    if url.origin != base or other.origin != other_base:
        # Following just one origin can mean a scheme-dependent relative URL or
        # an external URL whose host happens to match that base. A third host
        # with the matching scheme distinguishes them through the same parser.
        for resolved, origin in ((url, base), (other, other_base)):
            if resolved.origin == origin:
                same_scheme_base = resolved.protocol + "//reference.invalid"
                if (
                    URL(specifier, same_scheme_base + importer_url).origin
                    == same_scheme_base
                ):
                    raise ReferenceError("dependency-scheme-dependent")
        return None
    # Fragment-only references follow the base's filename too. An explicit
    # self-resource URL does not follow the other filename and remains captured.
    if (
        "#" in url.href
        and not url.search
        and url.pathname == importer_url
        and other.pathname == other_importer_url
    ):
        return None
    if module and ("?" in url.href or "#" in url.href):
        raise ReferenceError("dependency-not-local")
    path = unquote(url.pathname)
    if "\\" in path or any(ord(char) < 32 for char in path):
        raise ReferenceError("dependency-encoded")
    resolved = posixpath.normpath(path)
    if resolved.startswith("//") or not resolved.startswith("/"):
        raise ReferenceError("dependency-escapes")
    # A module is JavaScript, or JSON its import reads `with { type: "json" }`, as
    # the runtime reads its kernel registry; the browser refuses JSON imported
    # without it, which a page's render check reports as a console error.
    if module and Path(resolved).suffix not in {*JAVASCRIPT_SUFFIXES, ".json"}:
        raise ReferenceError("module-type")
    return resolved, url.search + url.hash


PUBLIC_MODULES = tuple(kernel_registry()["$public-modules"]["paths"])


def dependency_reference(
    specifier: str, importer: str, *, module=False
) -> tuple[str, str] | None:
    """Read a resource URL, reporting refusal in its capture source."""
    try:
        return resource_reference(specifier, importer, module=module)
    except ReferenceError as error:
        raise artifact_error(error.code, importer, specifier, **error.values) from error


def resolve_dependency(specifier: str, importer: str, *, module=False) -> str | None:
    """Admit an authored resource to the files or public entry points a revision holds."""
    reference = dependency_reference(specifier, importer, module=module)
    if reference is None:
        return None
    resolved, _suffix = reference
    if module:
        if not resolved.startswith("/page/") and resolved not in PUBLIC_MODULES:
            raise artifact_error("module-outside-page", importer, specifier)
    elif not resolved.startswith(("/page/", "/media/")):
        raise artifact_error("dependency-outside-page", importer, specifier)
    return resolved


def authored_imports(
    data: bytes, path: str, refused: list[Finding] | None = None
) -> tuple[tuple[int, int, str], ...]:
    """Each literal import of the authored module at `path`, as its span and the page
    file or public entry point it resolves to (`resolve_dependency`), less those that
    load from another server. Each import it refuses, as `javascript_imports` reads it
    or as the gate admits it, is added to `refused`, and the rest are returned;
    without a list to collect them, every refused import is raised together."""
    problems: list[Finding] = []
    imports = []
    for start, end, specifier in javascript_imports(data, path, problems):
        try:
            target = resolve_dependency(specifier, path, module=True)
        except ArtifactError as error:
            problems.extend(error.findings)
            continue
        if target is not None:
            imports.append((start, end, target))
    if refused is not None:
        refused.extend(problems)
    elif problems:
        raise ArtifactError(problems)
    return tuple(imports)


def javascript_imports(
    data: bytes, path: str, refused: list[Finding] | None = None
) -> tuple[tuple[int, int, str], ...]:
    """The exact string-literal spans of static exports/imports and import().

    A computed import() binds when it runs, so capture neither follows nor refuses it:
    a CDN module named that way loads, and a page file it names is in the revision
    as every file under `page/` is (`revision_artifact.page_files`).

    This reads imports, not syntax: the browser judges the module, and its error
    reaches the agent through `page check` or the watcher.

    An import it refuses is added to `refused`, and the rest are returned; without a
    list to collect them, every refused import is raised together."""
    imports, problems = _javascript_imports(data, path)
    if refused is not None:
        refused.extend(problems)
    elif problems:
        raise ArtifactError(list(problems))
    return imports


@lru_cache(maxsize=512)
def _javascript_imports(data: bytes, path: str):
    """`javascript_imports`, with the imports it refuses beside the rest.

    A layer's modules are the same bytes in every page that selects them, and parsing
    a vendored bundle is costly, so a process reads each module once."""
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return (), (capture_finding("script-not-utf8", path),)
    from tree_sitter import QueryCursor

    parser, import_nodes = _javascript_reader()
    tree = parser.parse(data)
    # Document order, a node before the nodes it holds, as a walk of the tree meets
    # them, so the spans come back in the order the file states them.
    nodes = sorted(
        QueryCursor(import_nodes).captures(tree.root_node).get("node", []),
        key=lambda node: (node.start_byte, -node.end_byte),
    )
    imports = []
    refused = []
    for node in nodes:
        literal = None
        if node.type in {"import_statement", "export_statement"}:
            literal = node.child_by_field_name("source")
        elif node.type == "call_expression":
            function = node.child_by_field_name("function")
            # A tree the parser recovered from may lack the arguments.
            if (
                function is not None
                and function.type == "import"
                and (arguments := node.child_by_field_name("arguments"))
            ):
                literal = next(
                    (child for child in arguments.named_children if not child.is_extra),
                    None,
                )
        if literal is not None and literal.type == "string":
            specifier = data[literal.start_byte + 1 : literal.end_byte - 1].decode(
                "utf-8"
            )
            # These are JavaScript literals, not HTML resource URLs. The reader
            # does not decode JS string escapes, and bare imports require a map.
            if "\\" in specifier:
                refused.append(capture_finding("dependency-not-local", path, specifier))
                continue
            absolute = URL.parse(specifier)
            if absolute is not None:
                specifier = absolute.href
            elif not specifier.startswith(("/", "./", "../")):
                refused.append(capture_finding("module-not-local", path, specifier))
                continue
            imports.append((literal.start_byte, literal.end_byte, specifier))
    return tuple(imports), tuple(refused)


@cache
def _javascript_reader():
    """Tree-sitter's JavaScript parser and the query for the nodes `javascript_imports`
    reads, matched in the parser's own code rather than by visiting every node of a
    vendored bundle in Python. Built when a module is first read: most processes
    (every hook) never read one, and the imports cost tens of milliseconds."""
    import tree_sitter_javascript
    from tree_sitter import Language, Parser, Query

    language = Language(tree_sitter_javascript.language())
    query = Query(
        language,
        "(import_statement) @node (export_statement) @node "
        "(call_expression function: (import)) @node",
    )
    return Parser(language), query
