"""Layer input resolution, composition, and content identity.

A selection has two compositions, each held for the process by the inputs it
resolves to. Its vocabulary (`selected_vocabulary`, `LayerVocabulary`) is all a
reader of the page needs, merged and stamped but not validated. The full composition
(`selected_layer`, `LayerComposition`) is built over that vocabulary, validates its
registry, and reads and validates every sheet and module the layer serves;
`validation.command.cmd_check` and
`http.page_endpoint` compose it so that `page check` and `server start` refuse a
package that no longer composes (`layer-registry.md`)."""

import hashlib
import json
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import cache, cached_property, lru_cache
from pathlib import Path

from .files import file_stamp
from .findings import Finding
from .locations import first_overlap, located
from .machine import package_store
from .page_memory import once
from .refusals import Refused
from .registry.contract import MODULES, is_element_name
from .registry.kernel import kernel_protocol
from .schema import (
    ASSETS,
    BROWSER_DIRS,
    BUNDLED_PACKAGES,
    DEFAULT_PACKAGE,
    HTML_NAME,
    INSTRUCTIONS_DIR,
    INSTRUCTIONS_FILE,
    JAVASCRIPT_SUFFIXES,
    KERNEL,
    KERNEL_FILES,
    LAYER_TOP_FILES,
    PACKAGE_DIRS,
    PACKAGE_FILES,
    RUNTIME_DIRS,
    RUNTIME_ENTRY,
)
from .state import PLUGIN_ROOT, plugin_cache_copy


def named_package(name: str) -> Path | None:
    """Select one installed snapshot or the bundled package with this name.

    Installed names are atomically replaced symlinks into immutable snapshots. Resolve
    the link once, so a reader keeps one complete package even when another install
    publishes that name. An installed package deliberately overrides a bundled one.
    """
    installed = package_store() / "names" / name
    if installed.is_symlink():
        return installed.resolve(strict=True)
    bundled = BUNDLED_PACKAGES / name
    return bundled if bundled.is_dir() else None


def resolve_packages(selected: tuple[str, ...], base: Path) -> list[Path]:
    """Resolve package selections without changing their order.

    A bare name selects an installed or bundled package. Other relative paths
    resolve against `base`: the working directory of the `page init` naming them, or
    the page directory for the copies its record names (`vendoring`). A `~` path
    stays portable across the user's machines. Absolute paths are refused because
    `$layer.packages` is served with the page.
    """
    packages = []
    for value in selected:
        if re.fullmatch(HTML_NAME, value):
            named = named_package(value)
            if named is None:
                raise Refused(
                    f"unknown package {value!r}; run `leaf package install` to add "
                    f"it, or use './{value}' for a project-relative package path"
                )
            if named != DEFAULT_PACKAGE:
                packages.append(named)
            continue
        package_path = Path(value)
        if package_path.is_absolute():
            raise Refused(
                f"package {value!r} is absolute; use a bundled name, "
                "explicit project-relative path, or ~ path so the page "
                "does not publish a machine path"
            )
        root = package_path.expanduser()
        if not root.is_absolute():
            root = base / root
        if not (root.exists() or root.is_symlink()):
            raise Refused(f"package {value!r} is not a directory")
        packages.append(root)
    return packages


def layer_inputs(
    selected: tuple[str, ...] = (), base: Path | None = None
) -> list[Path]:
    """The kernel, bundled default, and explicitly selected packages, in order, a
    path selection resolving against `base` or else the working directory."""
    return [ASSETS, DEFAULT_PACKAGE, *resolve_packages(selected, base or Path.cwd())]


def checked_inputs(inputs: list[Path]) -> list[Path]:
    """Existing, structurally valid kernel and package roots.

    A path of the wrong kind is authored input, not an absent package.
    Refuse it here once so every merger can assume the public directory contract.
    """
    roots = []
    for root in inputs:
        if not (root.exists() or root.is_symlink()):
            continue
        if not root.is_dir():
            raise Refused(f"{root} must be a directory")
        for name in KERNEL_FILES if root == ASSETS else PACKAGE_FILES:
            path = root / name
            if (path.exists() or path.is_symlink()) and not path.is_file():
                raise Refused(f"{path} must be a file")
        for sub in PACKAGE_DIRS:
            directory = root / sub
            if not (directory.exists() or directory.is_symlink()):
                continue
            if not directory.is_dir():
                raise Refused(f"{directory} must be a directory")
            if sub == INSTRUCTIONS_DIR:
                for path in directory.iterdir():
                    if not path.is_file():
                        raise Refused(f"{path} must be a file")
                    if not INSTRUCTIONS_FILE.fullmatch(path.name):
                        raise Refused(f"{path} must be named <audience>.md")
                continue
            for path in directory.rglob("*"):
                if path.is_dir() and not path.is_symlink():
                    continue
                if not path.is_file():
                    raise Refused(f"{path} must be a file or real directory")
        roots.append(root)
    return roots


def input_paths(inputs: list[Path]) -> list[Path]:
    """Every path a layer input reads, including nested symlink targets."""
    paths = []
    for root in inputs:
        paths.append(root.resolve())
        paths.extend(
            path.resolve()
            for name in (KERNEL_FILES if root == ASSETS else PACKAGE_FILES)
            if ((path := root / name).exists() or path.is_symlink())
        )
        paths.extend(
            imported
            for sheet in sorted(root.glob("*.css"))
            for imported in imported_sheets(sheet, root)
        )
        for sub in PACKAGE_DIRS:
            directory = root / sub
            if not (directory.exists() or directory.is_symlink()):
                continue
            paths.append(directory.resolve())
            if directory.is_dir():
                entries = (
                    directory.iterdir()
                    if sub == INSTRUCTIONS_DIR
                    else directory.rglob("*")
                )
                paths.extend(path.resolve() for path in entries)
    return paths


def overlapping_inputs(inputs: list[Path]):
    """The first resolved path shared by two precedence scopes."""
    located_inputs = [(root, located(input_paths([root]))) for root in inputs]
    for index, (left_root, left_paths) in enumerate(located_inputs):
        for right_root, right_paths in located_inputs[index + 1 :]:
            if overlap := first_overlap(left_paths, right_paths):
                left, right = overlap
                return left_root, left, right_root, right
    return None


def composed_dir_files(inputs: list[Path], sub: str) -> dict[str, Path]:
    """The winning input for every file in one composed directory."""
    winners = {}
    for root in inputs:
        source_dir = root / sub
        if not source_dir.is_dir():
            continue
        for path in sorted(source_dir.rglob("*")):
            if path.is_file():
                winners[path.relative_to(source_dir).as_posix()] = path
    return winners


# The document's cascade tiers, lowest first. The chrome's form-control clearing
# (`lf-reset`, runtime/chrome.css) stays below everything that chooses a face, as does a
# shadow tree's default control face (styles/control-face.css). The
# kernel, every widget package, and each widget module's adopted sheet
# (runtime/base-layer.js) share one layer, so specificity, then order, rank their
# rules. The kernel's Layouts sit above it. Package overrides
# sit above those defaults and the Layouts (`lf-overrides`), so a package
# styles every page the way the page's own sheet styles one.
# Semantic state follows: retirement must outrank a theme's or package's default box
# and a Layout's arrangement. The page's own sheet stays unlayered above these tiers,
# and inline widget motion outranks them too. Chrome and apparatus marks stay
# unlayered to beat page and widget alike; runtime/stylesheets.js owns their
# precedence and defaults. `lf-shadow` holds shared shadow rules and is read only in
# shadow trees, where it sits above adopted widget sheets and below package overrides.
CASCADE_LAYERS = (
    "lf-reset",
    "lf-base",
    "lf-layouts",
    "lf-shadow",
    "lf-overrides",
    "lf-state",
)

# tinycss2 currently decodes surrogate escapes to lone surrogates. CSS requires
# U+FFFD instead; keep its serialization valid UTF-8 until its tokenizer is fixed.
_CSS_SURROGATES = dict.fromkeys(range(0xD800, 0xE000), 0xFFFD)


def stylesheet(source: Path, root: Path) -> str:
    """One sheet as a page receives it: validated, its EOF recovery completed, its
    comments dropped, and each `@import` replaced by the sheet it names.

    A sheet's sources are what an author edits, so a sheet split into files needs no
    build and can never be served older than its parts. An import names a file inside
    `root`, relative to the importing sheet, optionally with `layer(name)`; its rules
    stand where the import stood, so a relative `url()` in them resolves against the
    page's copy of the importing sheet. The page then receives complete sheets and asks
    for no import, which an adopted sheet couldn't make anyway. A dependency's sheet,
    which an install has no `node_modules` to read, is bundled into a file beside its
    importer (`build/styles.mjs`).
    """
    return _stylesheet(source, root, ())


def _stylesheet(source: Path, root: Path, opened: tuple[Path, ...]) -> str:
    """`stylesheet`, inside the imports of `opened`."""
    opened = (*opened, source.resolve())
    try:
        css = source.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise Refused(f"{source} must be UTF-8") from error
    parts = []
    for part in _stylesheet_parts(css, source):
        if isinstance(part, str):
            parts.append(part)
        else:
            path, layer = _import(part, source, root, opened)
            sheet = _stylesheet(path, root, opened)
            parts.append(f"@layer {layer} {{\n{sheet}}}\n" if layer else sheet)
    serialized = "".join(parts).translate(_CSS_SURROGATES)
    return serialized if serialized.endswith("\n") else serialized + "\n"


@lru_cache(maxsize=512)
def _stylesheet_parts(css: str, source: Path) -> tuple:
    """One exact source's validated, normalized parts and read-only import rules.

    Only source-local work is held: every composition reads each source again and
    resolves its imports against that call's root and active import chain.
    """
    import tinycss2

    from .revision_artifact import css_syntax_errors
    from .styles import css_stylesheet

    # Maintained layer code refuses declarations the browser drops; page CSS
    # reports those as advice.
    if errors := css_syntax_errors(css, str(source)):
        raise Refused(str(errors[0]))
    return tuple(
        node if _is_import(node) else tinycss2.serialize([node])
        for node in css_stylesheet(css)
    )


def imported_sheets(source: Path, root: Path) -> list[Path]:
    """Every file `stylesheet(source, root)` reads besides `source`, for a reader that
    follows a sheet's inputs. An import composition would refuse is left out, since
    composing reports it."""
    return _imported_sheets(source, root, ())


def _imported_sheets(source: Path, root: Path, opened: tuple[Path, ...]) -> list[Path]:
    from .styles import css_stylesheet

    opened = (*opened, source.resolve())
    found = []
    try:
        rules = css_stylesheet(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return found
    for node in filter(_is_import, rules):
        try:
            path, _ = _import(node, source, root, opened)
        except Refused:
            continue
        found += [path, *_imported_sheets(path, root, opened)]
    return found


def _is_import(node) -> bool:
    return node.type == "at-rule" and node.lower_at_keyword == "import"


def _import(
    rule, source: Path, root: Path, opened: tuple[Path, ...]
) -> tuple[Path, str | None]:
    """The file one `@import` in `source` names, and the cascade layer it asks for.
    `opened` is the chain of sheets importing it, `source` last."""
    import tinycss2

    target, *conditions = [t for t in rule.prelude if t.type != "whitespace"] or [None]
    if target is not None and target.type == "function" and target.lower_name == "url":
        target = next((t for t in target.arguments if t.type == "string"), None)
    layer = None
    if conditions and getattr(conditions[0], "lower_name", None) == "layer":
        layer = tinycss2.serialize(conditions[0].arguments).strip() or None
    unplaced = conditions[1:] if layer else conditions
    if target is None or target.type not in ("string", "url") or unplaced:
        raise Refused(
            f"{source}: `@import {tinycss2.serialize(rule.prelude).strip()}` takes a "
            "file's relative path and at most `layer(name)`; wrap the imported rules in "
            "@media or @supports inside that file"
        )
    path = (source.parent / target.value).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise Refused(f"{source} imports {target.value!r}, which is no file in {root}")
    if path in opened:
        cycle = [*opened[opened.index(path) :], path]
        raise Refused("stylesheets import each other: " + " -> ".join(map(str, cycle)))
    return path, layer


# Where each style rule of a package's chrome.css stands: in the chrome's scope, so it
# matches only what the chrome holds, and under its root at two ids' weight, which no
# rule of Leaf's chrome carries.
CHROME_RESTYLE = "@scope (.lf-chrome) {{ :scope:not(#\\#):not(#\\#) {{ {} }} }}"
# The group rules whose own rules are rewritten too. Every other at-rule, such as
# @font-face, @keyframes or a @layer statement, stays as written where it stands.
CHROME_RESTYLE_GROUPS = frozenset(
    {"media", "supports", "container", "layer", "starting-style"}
)


def _holds_scope(nodes) -> bool:
    """Whether any rule among `nodes`, at any depth, is an @scope."""
    for node in nodes:
        keyword = getattr(node, "lower_at_keyword", None) or (
            node.lower_value if node.type == "at-keyword" else None
        )
        if keyword == "scope":
            return True
        for child in ("prelude", "content", "arguments"):
            if (tokens := getattr(node, child, None)) and _holds_scope(tokens):
                return True
    return False


def chrome_restyle(sheet: str, source: Path) -> str:
    """A package's chrome.css as the chrome's sheet takes it, above Leaf's own rules.

    The chrome's rules stand outside every layer, so they beat the page and every
    package; a theme restyles the chrome on purpose only from here. Each style rule,
    in its place and inside whatever conditions hold it, is nested in
    `CHROME_RESTYLE`, so it reaches only what the chrome holds and wins over Leaf's
    chrome rules whatever selector either writes. Nested, its selector is relative to
    the chrome's root, so one keyed on the page around the chrome places `&` for that
    root (`:root.dark & [part~="panel"]`). A rule inside a @layer stays layered, and so
    loses to every unlayered chrome rule. Any other at-rule is global, as anywhere in
    CSS. A package names what it restyles by part (`[part~="panel"]`), the chrome's
    public names for its surfaces; its other classes are private and change without
    notice. What the browser would drop as invalid is dropped here too, a rule whose
    selector holds `;` included, which nesting would read as a declaration and a rule.

    A sheet holding @scope is refused: at its top it would set a scope of its own
    beside the chrome's, reaching the page, and nested in a rule Chromium matches
    nothing in it.
    """
    import tinycss2

    from .styles import css_stylesheet

    if _holds_scope(css_stylesheet(sheet)):
        raise Refused(
            f"{source} holds @scope; Leaf already scopes chrome.css to its chrome, "
            "so write its rules without one"
        )

    def restyled(nodes):
        parts = []
        for node in nodes:
            # A `;` in a selector makes it invalid where it stands, but once nested
            # it would end a declaration and leave the rest a rule of its own.
            if node.type == "error" or (
                node.type == "qualified-rule"
                and any(token == ";" for token in node.prelude)
            ):
                continue
            if node.type == "qualified-rule":
                parts.append(CHROME_RESTYLE.format(tinycss2.serialize([node])))
            elif (
                node.type == "at-rule"
                and node.content is not None
                and node.lower_at_keyword in CHROME_RESTYLE_GROUPS
            ):
                inner = restyled(tinycss2.parse_rule_list(node.content))
                prelude = tinycss2.serialize(node.prelude)
                parts.append(f"@{node.at_keyword}{prelude}{{{inner}}}")
            else:
                parts.append(tinycss2.serialize([node]))
        return "".join(parts)

    return restyled(css_stylesheet(sheet))


def composed_sheets(inputs: list[Path]) -> dict[str, bytes]:
    """The layer's three stylesheets: each contribution in its role's cascade tier,
    in input order. Leaf places sheets and rewrites none of their rules but
    chrome.css's, which it nests in the chrome (`chrome_restyle`).

    A sheet's filename sets its role. defaults.css holds a package's defaults in
    lf-base, below Layouts: a widget's own, and a theme's element rules and idioms,
    such as the bundled `reading` look. A thread's transcript holds layer markup
    wherever it is drawn, and a widget can seat one in its shadow tree, such as a
    diff's line threads, so every shadow tree also takes defaults.css within
    `@scope (.lf-thread-transcript)`, in lf-shadow after the package's
    widget-shadow.css, the order and tier it holds against the shared sheets in the
    document: a message's markup wears its packages' look there as in the document,
    and the tree's own elements take none of it.
    widget-shadow.css holds rules for both trees, in lf-base in the
    document and lf-shadow in every declared shadow tree. Leaf adds no scope around
    either, so each names the widgets it styles: by tag in the document, and by
    `:host(tag)` in a shadow tree, where a rule reaches everything the tree holds,
    including core views placed there, such as a diff's threads. overrides.css
    holds rules meant to win over every package's defaults and the Layouts, in
    lf-overrides. A theme reaches shadow trees through the custom properties they
    inherit. chrome.css restyles Leaf's chrome, which takes it above its own rules
    (`chrome_restyle`, `revision_delivery.delivery_sheets`). Each sheet
    is read with its relative imports (`stylesheet`).

    The kernel supplies the base and shared shadow defaults. The default face of a
    native control (styles/control-face.css) heads lf-base in the document and stands
    in lf-reset in a shadow tree, below the rules a widget adopts there, as that
    sheet's header explains. The kernel's Layouts and semantic state retain their own
    tiers. Page CSS remains unlayered.
    """
    kernel, *packages = inputs
    if not (kernel / "base.css").is_file():
        raise Refused("the incoming layer has no base.css")
    order = f"@layer {', '.join(CASCADE_LAYERS)};\n"
    theme = [order]
    shadow = [order]
    chrome = []

    def place(sheets, tier, root, name):
        source = root / name
        if source.is_file():
            sheets.append(f"@layer {tier} {{\n{stylesheet(source, root)}}}\n")

    if (leading := kernel / "styles/shadow-leading.css").is_file():
        shadow.insert(0, stylesheet(leading, kernel))
    place(theme, "lf-base", kernel, "styles/control-face.css")
    place(shadow, "lf-reset", kernel, "styles/control-face.css")
    place(theme, "lf-base", kernel, "shadow.css")
    place(shadow, "lf-shadow", kernel, "shadow.css")
    place(theme, "lf-base", kernel, "base.css")
    for root in packages:
        place(theme, "lf-base", root, "widget-shadow.css")
        place(shadow, "lf-shadow", root, "widget-shadow.css")
        place(theme, "lf-base", root, "defaults.css")
        if (source := root / "defaults.css").is_file():
            shadow.append(
                f"@layer lf-shadow {{\n@scope (.lf-thread-transcript) {{\n"
                f"{stylesheet(source, root)}}}\n}}\n"
            )
        place(theme, "lf-overrides", root, "overrides.css")
        if (source := root / "chrome.css").is_file():
            chrome.append(chrome_restyle(stylesheet(source, root), source))
    for name in ("layouts.css", "state.css"):
        if (source := kernel / name).is_file():
            sheet = stylesheet(source, kernel)
            theme.append(sheet)
            if name == "state.css":
                shadow.append(sheet)
    return {
        "theme.css": "".join(theme).encode(),
        "shadow.css": "".join(shadow).encode(),
        "chrome.css": "".join(chrome).encode(),
    }


def portable_sheet(inputs: list[Path], tags: list[str]) -> bytes:
    """The look a page without Leaf links for the widgets it runs (module-authoring.md,
    "A widget that also runs off Leaf"), served as the layer's portable.css.

    It holds the kernel's tokens, Web Awesome's (its theme's custom properties) and
    Leaf's values for them, since the faces Leaf takes from that library read them,
    then the default control face and the kernel's shared sheet (styles/control-face.css,
    shadow.css) nested under `:where(<the layer's tags>)`, then the sheets of each package that ships
    widgets (widget-shadow.css and defaults.css), all in lf-base, the tier a widget
    module's adopted rules take off Leaf too (runtime/base-layer.js). The nesting keeps
    the shared sheet's page-wide faces (a native control's font, and the faces a Leaf
    page's own controls take by name, such as `.lf-btn`) to the widgets' insides, so
    the host's own markup keeps its look; it adds no
    specificity and keeps each rule's order, so a widget's insides rank as on a Leaf
    page. A rule there that reaches the widget element itself, or declares on `:root`,
    reaches nothing on the host, which is why the tokens stand outside it. The shared
    sheet's `@property` and `@keyframes` rules can't nest, so they never reach a host
    either: a thread's sheen and the registration of custom properties a widget's look
    there doesn't rest on, as tests/smoke/test_plain_page.py holds.
    A package
    that ships no widgets, such as a theme, styles a page rather than its widgets, so
    it stays out, as do base.css's page shell, the Layouts, semantic state and every
    overrides.css and chrome.css. The host's unlayered rules outrank all of it.
    """
    kernel, *packages = inputs
    parts = []

    def place(sheet):
        parts.append(f"@layer lf-base {{\n{sheet}}}\n")

    for name in (
        "styles/vendor/webawesome-theme.css",
        "styles/tokens.css",
        "styles/webawesome-tokens.css",
    ):
        if (tokens := kernel / name).is_file():
            place(stylesheet(tokens, kernel))
    if (shared := kernel / "shadow.css").is_file() and tags:
        face = stylesheet(kernel / "styles/control-face.css", kernel)
        place(f":where({', '.join(tags)}) {{\n{face}{stylesheet(shared, kernel)}}}\n")
    for root in packages:
        if not (root / "widgets").is_dir():
            continue
        for name in ("widget-shadow.css", "defaults.css"):
            if (source := root / name).is_file():
                place(stylesheet(source, root))
    return "".join(parts).encode()


def composed_instructions(inputs: list[Path]) -> dict[str, bytes]:
    """Package instructions joined by audience in layer precedence order.

    Each package's passage opens under a heading naming its package, so a guide
    file starts with its first rule rather than a title of its own, and one
    package's text never reads as part of the package before it.
    """
    parts: dict[str, list[str]] = {}
    for root in inputs:
        directory = root / INSTRUCTIONS_DIR
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            if not path.is_file():
                continue
            try:
                instructions = path.read_text(encoding="utf-8")
            except UnicodeDecodeError as error:
                raise Refused(f"{path} must be UTF-8") from error
            if instructions.strip():
                parts.setdefault(path.name, []).append(
                    f"# Package `{root.name}`\n\n{instructions.strip()}\n"
                )
    return {name: "\n".join(passages).encode() for name, passages in parts.items()}


def checked_layer_inputs(inputs: list[Path]) -> list[Path]:
    """Structurally valid, non-overlapping inputs in composition order."""
    roots = checked_inputs(inputs)
    if overlap := overlapping_inputs(roots):
        left_root, left, right_root, right = overlap
        raise Refused(
            f"layer inputs {left_root} and {right_root} overlap at {left} and "
            f"{right}; package scopes must be separate"
        )
    return roots


def kernel_runtime_paths() -> set[str]:
    """Private kernel paths packages cannot replace: the source modules and the
    compiled kernel's, so one boundary holds whichever a page runs."""
    return {
        path.relative_to(root / "runtime").as_posix()
        for root in (ASSETS, KERNEL)
        for path in (root / "runtime").rglob("*.js")
    }


@dataclass(frozen=True, eq=False)
class LayerVocabulary:
    """The part of a layer a reader of a page needs: the merged registry, the paths
    of the files the layer's `widgets/` directory serves, and the packages'
    instructions by audience file (`composed_instructions`).

    Reading a page's documents, state or instructions needs only this
    (`registry.storage.page_vocabulary`, `page.page_instructions`), so it is composed
    apart from the layer's files (`LayerComposition`), which Leaf parses only to
    serve, export, check or inspect a page, or to capture a revision whose markup
    names one of them."""

    registry: dict
    widgets: frozenset[str]
    instructions: dict[str, bytes]
    # What readers derive from this vocabulary, such as a revision's
    # (`registry.storage.revision_vocabulary`), held for as long as it is, each
    # made once (`page_memory.once`).
    readings: dict = field(default_factory=dict, repr=False)


@dataclass(frozen=True, eq=False)
class LayerComposition:
    vocabulary: LayerVocabulary
    top_files: dict[str, bytes]
    directory_files: dict[str, dict[str, bytes]]

    @cached_property
    def fingerprint(self) -> str:
        return layer_fingerprint(self)

    @property
    def files(self) -> dict[str, bytes]:
        """Every file the layer serves, by its rooted page path."""
        return {
            **{f"/{name}": data for name, data in self.top_files.items()},
            **{
                f"/{directory}/{name}": data
                for directory, entries in self.directory_files.items()
                for name, data in entries.items()
            },
        }


def selected_layer(
    packages: tuple[str, ...], theme: str | None, page_dir: Path
) -> LayerComposition:
    """The layer this Leaf composes for the page at `page_dir` that selects
    `packages` and the `theme`, composed before them: its core and
    bundled packages, the user's installed ones, as this process first read them,
    and the copies the page holds of packages it selects by path.

    A page records only its selection (`registry.storage.LAYER`), so every Leaf
    that serves, checks or exports it composes its own layer, the way it supplies
    its own runtime (`runtime_selection`). Held for the process, since a plugin
    update may replace the tree under a running server, which keeps answering with
    the bytes it started with. Held by the package roots the selection resolves to
    rather than its spelling, since a page's own copy is another directory in another
    page, and an installed name another snapshot after `package install`; and a
    page's copy by its stamp too, since its next `page init` replaces it in place."""
    return _composed(*_selection(packages, theme, page_dir))


def selected_vocabulary(
    packages: tuple[str, ...], theme: str | None, page_dir: Path
) -> LayerVocabulary:
    """The vocabulary of the layer `selected_layer` composes for the same selection,
    without reading the layer's files. Held for the process, as the layer is."""
    return _vocabulary(*_selection(packages, theme, page_dir))


def _selection(
    packages: tuple[str, ...], theme: str | None, page_dir: Path
) -> tuple[tuple[Path, ...], tuple]:
    """The inputs a selection resolves to, and the stamps of the page's own copies
    among them: what `selected_layer` and `selected_vocabulary` hold a layer by."""
    if theme is not None:
        packages = (theme, *(name for name in packages if name != theme))
    inputs = tuple(layer_inputs(packages, page_dir))
    copies = tuple(file_stamp(root) for root in inputs if root.is_relative_to(page_dir))
    return inputs, copies


_vocabularies: dict = {}
_compositions: dict = {}


def _vocabulary(inputs: tuple[Path, ...], copies: tuple) -> LayerVocabulary:
    return once(
        _vocabularies,
        (inputs, copies),
        lambda: compose_vocabulary(checked_inputs(list(inputs))),
    )


def _composed(inputs: tuple[Path, ...], copies: tuple) -> LayerComposition:
    return once(
        _compositions,
        (inputs, copies),
        lambda: _composition(
            checked_layer_inputs(list(inputs)), lambda: _vocabulary(inputs, copies)
        ),
    )


def files_identity(files: dict[str, bytes]) -> str:
    """Identify a set of named bytes, unambiguously across names and contents."""
    digest = hashlib.sha256()
    for name in sorted(files):
        encoded = name.encode()
        data = files[name]
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return f"sha256:{digest.hexdigest()}"


def layer_fingerprint(composition: LayerComposition) -> str:
    """Identify the complete composed layer independently of its generation."""
    return files_identity(
        {
            **composition.top_files,
            "registry.json": json.dumps(
                composition.vocabulary.registry,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode(),
            **{
                f"{directory}/{name}": data
                for directory, entries in composition.directory_files.items()
                for name, data in entries.items()
            },
            **{
                f"{INSTRUCTIONS_DIR}/{name}": data
                for name, data in composition.vocabulary.instructions.items()
            },
        }
    )


def payload_python_inputs(root: Path) -> list[Path]:
    """Code, schemas and dependencies a running Python process has loaded."""
    return [
        *sorted(path for path in (root / "src").rglob("*.py") if path.is_file()),
        *sorted(path for path in (root / "src").rglob("*.json") if path.is_file()),
        root / "browser/registry.json",
        root / "pyproject.toml",
        root / "uv.lock",
    ]


def payload_server_inputs(root: Path) -> list[Path]:
    """The serving code, the browser runtime it serves (`runtime_selection`), and the
    dependency manifests an init must restart to adopt."""
    runtime = [
        root / "browser" / RUNTIME_ENTRY,
        *(root / "browser" / name for name in RUNTIME_DIRS),
        root / "dist/kernel",
        root / "src/leaf/render-checks",
    ]
    served = sorted(
        path
        for top in runtime
        for path in ([top] if top.is_file() else top.rglob("*"))
        if path.is_file()
    )
    return [
        *payload_python_inputs(root),
        *served,
        *(
            sheet
            for path in served
            if path.suffix == ".css"
            for sheet in imported_sheets(path, root / "browser")
        ),
    ]


def incompatible_layer(page_dir: Path, record: dict) -> Finding | None:
    """Why this Leaf can neither serve a page nor write its log, given the page's
    layer record (`registry.storage.LAYER`); None when it may. The record names the
    page protocol a Leaf last initialized the page at, and this Leaf serves and
    writes only a page at its own (`registry.kernel.kernel_protocol`).

    The page's layer is composed by whichever Leaf reads it (`selected_layer`), so
    the protocol covers only what a page keeps across Leaf versions: its event log
    and the records kept outside it (`layer-registry.md`, "Page protocol"). A page
    at a higher number is refused as `newer-layer` (`newer_layer`), as is one whose
    layer record a newer Leaf wrote at a later shape, before this reading
    (`registry.storage.layer_record`), since its repair is a newer Leaf: this one
    does not take it down (`vendoring._plan_page`). For a page at an
    older number, the holding session's prompt and Stop hooks, and each of its
    commands that names the page, take it to this Leaf's number first
    (`vendoring.renew_layer`). Every server of the page's files, the website's
    included (`http.page_endpoint`, `leaf_website.page_binding`), the one append
    door and the writers that ask it first (`event_contracts.write_refusal`), and
    `page check` refuse on this one reading, each naming its repair."""
    recorded = record.get("protocol")
    if type(recorded) is int and recorded == kernel_protocol():
        return None
    if type(recorded) is int and recorded > kernel_protocol():
        return newer_layer(page_dir)
    return Finding(
        "foreign-layer",
        values={
            "page": str(page_dir),
            "recorded": recorded if recorded is not None else "none",
            "leaf": str(PLUGIN_ROOT),
            "protocol": kernel_protocol(),
        },
    )


def newer_layer(page_dir: Path) -> Finding:
    """The refusal of a page a newer Leaf initialized, at a higher page protocol or
    a later shape of its layer record (`registry.storage.layer_record`). Its repair
    is that newer Leaf, since this one does not take the page down."""
    return Finding(
        "newer-layer",
        values={
            "page": str(page_dir),
            "leaf": str(PLUGIN_ROOT),
            "protocol": kernel_protocol(),
        },
    )


def payload_provenance(*, include_path: bool = False, root: Path | None = None) -> dict:
    """Describe the Leaf payload that is running this command, when its source can.

    Beside the commit, one of two dates says how old the payload is: `committed`,
    the commit's committer date, where Git can read it; or `installed`, when a harness
    copied the payload into its plugin cache without `.git`. Both are ISO 8601 with
    an offset. Developer preparations can pass `root` to read another checkout
    through the same provenance rules.
    """
    source = Path(__file__) if root is None else root / "src/leaf/layer.py"
    root = PLUGIN_ROOT if root is None else root.resolve()
    provenance: dict = {"path": str(root)} if include_path else {}
    distribution = root / "leaf-distribution.json"
    if distribution.is_file():
        published = json.loads(distribution.read_text())
        provenance.update(published["producer"])
        return provenance
    # Claude Code copies a marketplace plugin without its .git directory into a cache
    # whose final component is the resolved plugin version. Leaf leaves its manifest
    # version unset, so that component is the source commit SHA. The default root
    # follows this module: a newer sibling cannot change the running copy's identity.
    if plugin_cache_copy(root):
        # The copy stamps every file with the time it was made, and Leaf never
        # rewrites its own modules. A harness copies only the marketplace's newest
        # commit, one update sweep after it lands, so this dates the commit to
        # within that sweep; the commit date itself left with `.git`.
        installed = datetime.fromtimestamp(source.stat().st_mtime, UTC)
        provenance.update(
            commit=root.name,
            dirty=False,
            installed=installed.astimezone().isoformat(timespec="seconds"),
        )
        return provenance

    # Reading provenance must leave the payload untouched. Optional locks suppress
    # index writes; disabling fsmonitor also prevents Git from starting a daemon
    # whose socket would make Codex refuse the installed plugin's hook fingerprint.
    git = ["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-C", str(root)]
    try:
        identity = subprocess.run(
            [*git, "rev-parse", "--show-toplevel", "--short=12", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return provenance
    if identity.returncode != 0:
        return provenance
    lines = identity.stdout.splitlines()
    if len(lines) != 2 or Path(lines[0]).resolve() != root.resolve():
        return provenance
    provenance["commit"] = lines[1]
    provenance["committed"] = subprocess.run(
        [*git, "show", "--no-patch", "--format=%cI", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    try:
        dirty = subprocess.run(
            [
                *git,
                "status",
                "--porcelain",
                "--untracked-files=all",
                "--",
                ".",
                ":(top,exclude).codex-marketplace-install.json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return provenance
    if dirty.returncode == 0:
        provenance["dirty"] = bool(dirty.stdout)
    return provenance


@cache
def running_leaf() -> dict:
    """`payload_provenance` read once for this process, by its first page server as
    that server is built (`http.page_app`): the Leaf whose code the process runs,
    however its checkout moves on afterwards."""
    return payload_provenance()


def provenance_label(provenance: dict) -> str:
    """One line naming a payload's commit and date, as `payload_provenance` read it.

    `+` marks uncommitted changes, as About this page does.
    """
    commit = provenance.get("commit")
    if not commit:
        return "unknown source"
    label = commit + ("+" if provenance.get("dirty") else "")
    for kind in ("committed", "installed"):
        if kind in provenance:
            return f"{label}, {kind} {provenance[kind]}"
    return label


def compose_vocabulary(roots: list[Path]) -> LayerVocabulary:
    """Read the vocabulary of the layer checked inputs produce (`LayerVocabulary`).

    Its registry is merged and stamped but not validated. `page init` validated the
    selection, and every Leaf that serves, exports or checks the page validates it
    again when it composes the layer's files (`_composition`). A reader of the page
    doesn't validate it."""
    from .registry.layer import merged_registry, stamp_composition

    incoming = stamp_composition(merged_registry(roots)[0])
    widgets = frozenset(composed_dir_files(roots, "widgets"))
    return LayerVocabulary(incoming, widgets, composed_instructions(roots))


def compose_layer(roots: list[Path]) -> LayerComposition:
    """Read and validate the complete layer produced by checked inputs: its
    vocabulary (`compose_vocabulary`) and every file it serves.

    The kernel's own runtime, `leaf.js` and its `runtime/` and `vendor/` files, is
    not part of it: the Leaf serving a page supplies that (`runtime_selection`), so
    the layer holds what packages add beside it, and the registry, theme and widgets
    every root contributes."""
    return _composition(roots, lambda: compose_vocabulary(roots))


def _composition(
    roots: list[Path], vocabulary_of: Callable[[], LayerVocabulary]
) -> LayerComposition:
    """The layer `roots` produce: its registry validated as `page init` vendors it,
    then the vocabulary `vocabulary_of` composes, whose stamping reads the registry
    as valid, its modules checked for private kernel imports, and its sheets and
    browser files read."""
    from .revision_artifact import (
        PUBLIC_MODULES,
        dependency_reference,
        javascript_imports,
    )
    from .validation.composition import incoming_registry

    incoming_registry(roots)
    vocabulary = vocabulary_of()

    protected = kernel_runtime_paths()
    private_modules = {"/leaf.js", *(f"/runtime/{name}" for name in protected)} - set(
        PUBLIC_MODULES
    )
    # Every module path an import in the layer names.
    imported = set()
    for root in roots:
        if root.resolve() == ASSETS.resolve():
            continue
        replacements = [
            f"runtime/{path.relative_to(root / 'runtime').as_posix()}"
            for path in (root / "runtime").rglob("*.js")
            if path.relative_to(root / "runtime").as_posix() in protected
        ]
        if (root / "leaf.js").exists():
            replacements.append("leaf.js")
        if replacements:
            raise Refused(
                f"package {root} replaces private kernel modules: "
                + ", ".join(sorted(replacements))
                + "; use /runtime/widget-api.js and package-owned modules"
            )
        for sub in BROWSER_DIRS:
            for module in (root / sub).rglob("*"):
                if not module.is_file() or module.suffix not in JAVASCRIPT_SUFFIXES:
                    continue
                path = "/" + module.relative_to(root).as_posix()
                for _, _, specifier in javascript_imports(module.read_bytes(), path):
                    dependency = dependency_reference(specifier, path, module=True)
                    if dependency is not None:
                        imported.add(dependency[0])
                    if dependency is not None and dependency[0] in private_modules:
                        raise Refused(
                            f"{module} imports private kernel module {specifier!r}; "
                            "use /runtime/widget-api.js"
                        )
    # A module named as a widget's is loaded because its tag is declared or because
    # another module imports it, as `lf-options.js` imports `lf-options-settled.js`.
    # One that neither holds for is a widget's module under the wrong name, a typo or
    # a tag renamed in the registry alone, and its widget would draw as plain markup
    # with nothing else to say so.
    loaded = set(vocabulary.registry[MODULES].values())
    unloaded = sorted(
        name
        for name in vocabulary.widgets
        if is_element_name(name.removesuffix(".js"))
        and name.endswith(".js")
        and f"widgets/{name}" not in loaded
        and f"/widgets/{name}" not in imported
    )
    if unloaded:
        raise Refused(
            "nothing loads these modules: no declared tag has the name and no module "
            "imports them. A widget's module is `widgets/<tag>.js`:\n"
            + "\n".join(f"  - widgets/{name}" for name in unloaded)
        )
    directory_sources = {
        sub: composed_dir_files(
            [
                root
                for root in roots
                if sub not in RUNTIME_DIRS or root.resolve() != ASSETS.resolve()
            ],
            sub,
        )
        for sub in BROWSER_DIRS
    }
    top_files = composed_sheets(roots) | {
        "portable.css": portable_sheet(
            roots, sorted(filter(is_element_name, vocabulary.registry))
        )
    }
    for name in LAYER_TOP_FILES:
        if name == "registry.json" or name in top_files:
            continue
        source = next(
            (source / name for source in reversed(roots) if (source / name).is_file()),
            None,
        )
        if source is None:
            raise Refused(f"the incoming layer has no {name}")
        top_files[name] = source.read_bytes()
    directory_files = {
        sub: {
            name: source.read_bytes() for name, source in directory_sources[sub].items()
        }
        for sub in BROWSER_DIRS
    }
    return LayerComposition(vocabulary, top_files, directory_files)
