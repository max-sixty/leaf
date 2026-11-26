"""Layer input resolution, composition and content identity, and which Leaf runs:
this process (`running_leaf`) and a page's server (`other_serving_leaf`).

A page's layer record (`registry.storage.LAYER`) selects two compositions, held
together by the inputs the selection resolves to, for the process or in the page's
memory (`_held`), and each is refused as a registry fault (`layer-unavailable`) where
the selection no longer resolves or composes. Its vocabulary (`selected_vocabulary`,
`LayerVocabulary`) is all a reader of the page needs, merged and stamped but not
validated. The full composition
(`selected_layer`, `LayerComposition`) is built over that vocabulary, validates its
registry, and reads and validates every sheet and module the layer serves;
`validation.command.cmd_check` and
`http.page_endpoint` compose it so that `page check` and `server start` refuse a
package that no longer composes (`layer-registry.md`)."""

import hashlib
import json
import re
import subprocess
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import cache, cached_property, lru_cache
from pathlib import Path

from leaf.base.files import file_stamp
from leaf.base.locations import first_overlap, located, paths_same
from leaf.base.machine import package_store
from leaf.base.page_memory import Stamped, memo, once
from leaf.base.refusals import Refused
from leaf.base.schema import (
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
from leaf.base.server import running_server
from leaf.base.state import PLUGIN_ROOT, installed_copy
from leaf.source.registry.contract import MODULES, is_element_name, registry_error
from leaf.source.registry.storage import layer_metadata_of


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


def selectable_packages() -> dict[str, Path]:
    """Each package a bare name selects, in name order, resolved as
    `named_package` resolves it: an installed package in place of a bundled one of
    its name."""
    names = {path.name for path in BUNDLED_PACKAGES.iterdir() if path.is_dir()}
    installed = package_store() / "names"
    if installed.is_dir():
        names |= {path.name for path in installed.iterdir()}
    return {
        name: root
        for name in sorted(names)
        if (root := named_package(name)) is not None
    }


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
                    f"unknown package {value!r}; `leaf package list` prints the names "
                    f"this machine can select, or use './{value}' for a "
                    "project-relative package path"
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


def package_layer_inputs(package: Path) -> list[Path]:
    """The layer a page selecting this package alone composes: the mandatory layer,
    then this package, once."""
    inputs = layer_inputs()
    if not any(paths_same(package, root) for root in inputs):
        inputs.append(package)
    return inputs


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
    """Every path the layer inputs read, each symlink resolved to its target:
    each input's root and its `_input_entries`."""
    return [path.resolve() for root in inputs for path in (root, *_input_entries(root))]


def package_files(root: Path) -> dict[str, bytes]:
    """The files of package `root` a layer composes (`_input_entries`), by their path
    in the package. A copy of a package is these files, so a page's copy and an
    installed one compose as the source does."""
    root = root.resolve()
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in _input_entries(root)
        if path.is_file()
    }


def _input_entries(root: Path) -> Iterator[Path]:
    """What layer input `root` holds that a layer reads (`checked_inputs`): its top
    files, every sheet one of its sheets imports, wherever in the input that stands
    (`stylesheet`), and each of its directories with what it holds. Each path is
    listed whatever its kind, a dangling symlink included; `package_files` keeps the
    files."""
    for name in KERNEL_FILES if root == ASSETS else PACKAGE_FILES:
        path = root / name
        if not (path.exists() or path.is_symlink()):
            continue
        yield path
        if name.endswith(".css") and path.is_file():
            yield from imported_sheets(path, root)
    for sub in PACKAGE_DIRS:
        directory = root / sub
        if not (directory.exists() or directory.is_symlink()):
            continue
        yield directory
        if directory.is_dir():
            yield from sorted(
                directory.iterdir() if sub == INSTRUCTIONS_DIR else directory.rglob("*")
            )


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


# The document's cascade tiers rank each of Leaf's rules by whose element it styles, and
# seat a page's base layer between the two kinds. Rules for the author's own elements
# (`lf-theme`: the kernel's tokens and page shell, markup's reading face, the faces of
# the page's own controls, the marks and focus band Leaf draws on any element, and each
# package's theme.css) stand below the page's `base`. Leaf's rules for its own elements
# stand above it: the kernel's faces for Leaf's controls and surfaces, every widget
# package's defaults, and each widget module's adopted sheet
# (runtime/base/base-layer.js) share `lf-base`, so specificity, then order, rank their
# rules. The kernel's Layouts sit above it. Package overrides sit above those defaults
# and the Layouts (`lf-overrides`), so a package styles every page the way the page's
# own sheet styles one. Semantic state follows: retirement must outrank a package's
# default box and a Layout's arrangement. Inline widget motion outranks them too.
# Chrome and apparatus marks stay unlayered to beat page and widget alike;
# runtime/base/stylesheets.js owns their precedence and defaults. The chrome's
# form-control clearing (`lf-reset`, runtime/chrome.css) stays below everything that
# chooses a face.
#
# Two names a page may give its layers rank among Leaf's tiers. A reset zeroes margins,
# borders and control faces on every element, so `reset` stands under every tier and
# applies wherever neither Leaf nor the page's theme says anything. A framework's base
# layer holds its reset beside the author's own element rules, as Tailwind keeps
# preflight in `base`, so `base` outranks the theme's look for the author's content, an
# `h1` the author sized there included, and loses to Leaf's faces for what it draws. A
# cascade layer ranks where its name is first declared, and Leaf's theme leads the
# document's head, so this one statement places `reset` and `base` whichever page sheet
# names them later. Every other layer the page names follows Leaf's tiers and outranks
# them, as the page's unlayered rules do, so a framework's components and utilities
# restyle what Leaf draws. A shadow tree takes no page rule, so it names only Leaf's
# tiers (`SHADOW_LAYERS`), where `lf-shadow` holds shared shadow rules above adopted
# widget sheets and below package overrides.
PAGE_RESET_LAYER = "reset"
PAGE_BASE_LAYER = "base"
THEME_LAYERS = ("lf-reset", "lf-theme")
PART_LAYERS = ("lf-base", "lf-layouts", "lf-overrides", "lf-state")
SHADOW_LAYERS = (
    "lf-reset",
    "lf-base",
    "lf-layouts",
    "lf-shadow",
    "lf-overrides",
    "lf-state",
)
DOCUMENT_LAYERS = (PAGE_RESET_LAYER, *THEME_LAYERS, PAGE_BASE_LAYER, *PART_LAYERS)
DOCUMENT_LAYER_ORDER = f"@layer {', '.join(DOCUMENT_LAYERS)};\n"

# Text Leaf draws from markup, a thread's transcript and Markdown Leaf renders, wears
# markup's reading face whatever the page's theme (styles/components/reading.css). In the
# document that face stands in `lf-theme`, under the page's `base`, so the document also
# reads it scoped to this text at the head of `lf-base` (`composed_sheets`): a
# framework's reset there leaves a message's lists and code blocks as Leaf drew them,
# and the page's markup still takes the reset.
DRAWN_TEXT = ":where(.lf-thread-transcript, .lf-markdown-body)"

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

    from leaf.source.styles import css_stylesheet, css_syntax_errors

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
    from leaf.source.styles import css_stylesheet

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

    from leaf.source.styles import css_stylesheet

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

    A sheet's filename sets its role, by whose elements its rules style (`THEME_LAYERS`,
    `PART_LAYERS`). theme.css holds a theme's rules for the author's own content, such
    as the bundled `reading` look's, in lf-theme, below the page's `base` layer.
    defaults.css holds a package's defaults for what Leaf draws, its widgets' and its
    rules for Leaf's idioms and controls, in lf-base, above the page's `base` and below
    Layouts. A thread's transcript holds layer markup wherever it is drawn, and a widget
    can seat one in its shadow tree, such as a diff's line threads, so every shadow tree
    also takes theme.css and defaults.css within `@scope (.lf-thread-transcript)`, in
    lf-shadow after the package's widget-shadow.css, the order they hold against the
    shared sheets in the document: a message's markup wears its packages' look there as
    in the document, and the tree's own elements take none of it.
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

    The document reads every tier from theme.css, whose first rule orders them
    (`DOCUMENT_LAYER_ORDER`). The kernel supplies both halves: the faces of the
    author's own elements (styles/page-control-face.css, styles/markup.css) and
    base.css in lf-theme, and the faces of what Leaf draws (styles/control-face.css,
    styles/parts.css) and elements.css in lf-base, which opens with markup's reading
    face scoped to the text Leaf draws (`DRAWN_TEXT`). There the face's own layer
    makes it the lowest of lf-base, as it is the lowest of lf-theme. A shadow tree reads
    the shared halves together (shadow.css), and its native controls' default face
    (styles/control-face.css) stands in lf-reset there, below the rules a widget adopts,
    as that sheet's header explains. The kernel's Layouts and semantic state retain
    their own tiers. Page CSS remains unlayered.
    """
    kernel, *packages = inputs
    if not (kernel / "base.css").is_file():
        raise Refused("the incoming layer has no base.css")
    theme = [DOCUMENT_LAYER_ORDER]
    parts = []
    shadow = [f"@layer {', '.join(SHADOW_LAYERS)};\n"]
    chrome = []

    def place(sheets, tier, root, name):
        source = root / name
        if source.is_file():
            sheets.append(f"@layer {tier} {{\n{stylesheet(source, root)}}}\n")

    if (leading := kernel / "styles/shadow-leading.css").is_file():
        shadow.insert(0, stylesheet(leading, kernel))
    place(theme, "lf-theme", kernel, "styles/page-control-face.css")
    place(theme, "lf-theme", kernel, "styles/markup.css")
    place(theme, "lf-theme", kernel, "base.css")
    if (face := kernel / "styles/components/reading.css").is_file():
        parts.append(
            f"@layer lf-base {{\n@scope ({DRAWN_TEXT}) {{\n"
            f"{stylesheet(face, kernel)}}}\n}}\n"
        )
    place(parts, "lf-base", kernel, "styles/control-face.css")
    place(parts, "lf-base", kernel, "styles/parts.css")
    place(parts, "lf-base", kernel, "elements.css")
    place(shadow, "lf-reset", kernel, "styles/control-face.css")
    place(shadow, "lf-shadow", kernel, "shadow.css")
    for root in packages:
        place(theme, "lf-theme", root, "theme.css")
        place(parts, "lf-base", root, "widget-shadow.css")
        place(shadow, "lf-shadow", root, "widget-shadow.css")
        place(parts, "lf-base", root, "defaults.css")
        for name in ("theme.css", "defaults.css"):
            if (source := root / name).is_file():
                shadow.append(
                    f"@layer lf-shadow {{\n@scope (.lf-thread-transcript) {{\n"
                    f"{stylesheet(source, root)}}}\n}}\n"
                )
        place(parts, "lf-overrides", root, "overrides.css")
        if (source := root / "chrome.css").is_file():
            chrome.append(chrome_restyle(stylesheet(source, root), source))
    for name in ("layouts.css", "state.css"):
        if (source := kernel / name).is_file():
            sheet = stylesheet(source, kernel)
            parts.append(sheet)
            if name == "state.css":
                shadow.append(sheet)
    return {
        "theme.css": "".join((*theme, *parts)).encode(),
        "shadow.css": "".join(shadow).encode(),
        "chrome.css": "".join(chrome).encode(),
    }


def portable_sheet(inputs: list[Path], tags: list[str]) -> bytes:
    """The look a page without Leaf links for the widgets it runs (module-authoring.md,
    "A widget that also runs off Leaf"), served as the layer's portable.css.

    It holds the kernel's tokens, Web Awesome's (its theme's custom properties) and
    Leaf's values for them, since the faces Leaf takes from that library read them,
    then the default control faces and the kernel's shared sheet (styles/control-face.css,
    styles/page-control-face.css, shadow.css) nested under `:where(<the layer's tags>)`,
    then the sheets of each package that ships
    widgets (widget-shadow.css and defaults.css), all in lf-base, the tier a widget
    module's adopted rules take off Leaf too (runtime/base/base-layer.js). The nesting keeps
    the shared sheet's page-wide faces (a native control's font, and the faces a Leaf
    page's own controls take under its theme) to the widgets' insides, so
    the host's own markup keeps its look; it adds no
    specificity and keeps each rule's order, so a widget's insides rank as on a Leaf
    page. A rule there that reaches the widget element itself, or declares on `:root`,
    reaches nothing on the host, which is why the tokens stand outside it. The shared
    sheet's `@property` and `@keyframes` rules can't nest, so they never reach a host
    either: a thread's sheen and the registration of custom properties a widget's look
    there doesn't rest on, as tests/smoke/test_plain_page.py holds.
    A package
    that ships no widgets, such as a theme, styles a page rather than its widgets, so
    it stays out, as do every theme.css, base.css's page shell and elements.css, the
    Layouts, semantic state and every overrides.css and chrome.css. The host's unlayered rules outrank all of it.
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
        face = "".join(
            stylesheet(kernel / name, kernel)
            for name in ("styles/control-face.css", "styles/page-control-face.css")
        )
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
    (`vocabulary.page_vocabulary`, `page.page_instructions`), so it is composed
    apart from the layer's files (`LayerComposition`), which Leaf parses only to
    serve, export, check or inspect a page, or to capture a revision whose markup
    names one of them."""

    registry: dict
    widgets: frozenset[str]
    instructions: dict[str, bytes]


@dataclass(frozen=True, eq=False)
class LayerComposition:
    vocabulary: LayerVocabulary
    top_files: dict[str, bytes]
    directory_files: dict[str, dict[str, bytes]]

    @cached_property
    def fingerprint(self) -> str:
        return layer_fingerprint(self)

    @cached_property
    def files_digest(self) -> str:
        """Identify the bytes the layer serves (`files`), which a browser runs,
        without the instructions `fingerprint` names too."""
        return files_identity(self.files)

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


def selected_layer(record: dict, page_dir: Path) -> LayerComposition:
    """The layer, with every file it serves, that this Leaf composes to serve, export
    or check the page at `page_dir` whose layer record is `record`: the packages the
    record selects, in the order it lists them, from the core and bundled packages,
    the user's installed ones, as this process first read them, and the copies the
    page holds of packages it selects by path. Refused as a registry fault where a
    selected package is gone or invalid.

    A page records only its selection (`registry.storage.LAYER`), so every Leaf
    that serves, checks or exports it composes its own layer, the way it supplies
    its own runtime (`runtime_selection`). The layer is held by the package roots
    the selection resolves to rather than its spelling, since an installed name
    resolves to another snapshot after `package install`; `_held` says for how
    long."""
    try:
        inputs, held = _held(tuple(record["packages"]), page_dir)
        return once(
            held,
            "layer",
            lambda: _composition(
                checked_layer_inputs(list(inputs)), lambda: _vocabulary(inputs, held)
            ),
        )
    except Refused as error:
        raise registry_error("layer-unavailable", error=str(error)) from None


def selected_vocabulary(record: dict, page_dir: Path) -> LayerVocabulary:
    """The vocabulary of the layer `selected_layer` composes for the same record, all
    a reader of the page's documents needs, without reading the layer's files, held
    with that layer. Refused as `selected_layer` refuses a selected package that is
    gone or whose registry can't be read or merged. Its registry is not validated
    (`compose_vocabulary`).

    Each call resolves the selection anew, and a `package install` between two calls
    points an installed name at another snapshot (`named_package`). So a reading that
    needs several of the layer's facts takes them all from one call, which it passes
    to `layer_vocabulary` and `layer_widgets`."""
    try:
        return _vocabulary(*_held(tuple(record["packages"]), page_dir))
    except Refused as error:
        raise registry_error("layer-unavailable", error=str(error)) from None


def layer_vocabulary(record: dict, vocabulary: LayerVocabulary) -> dict:
    """The registry of `vocabulary`, the layer `record` selects, with the selection
    and the generation the browser speaks under `$layer`. Each call makes a new copy
    of the layer's registry, sharing its entries."""
    return {**vocabulary.registry, "$layer": layer_metadata_of(record)}


def layer_widgets(vocabulary: LayerVocabulary) -> list[str]:
    """The page-root-relative widget entry modules the layer of `vocabulary` serves."""
    return sorted(
        f"widgets/{name}"
        for name in vocabulary.widgets
        if re.fullmatch(r"lf-[^/]*\.js", name)
    )


def served_layer(metadata: dict, page_dir: Path) -> dict:
    """`metadata` as the served state names the layer the page at `page_dir` is read
    under: with the fingerprint of the layer this Leaf composes for it, and this Leaf
    as its producer, the one About this page shows (`runtime/panel/page-about.js`)."""
    return {
        **metadata,
        "fingerprint": selected_layer(metadata, page_dir).fingerprint,
        "producer": running_leaf(),
    }


def _vocabulary(inputs: tuple[Path, ...], held: dict) -> LayerVocabulary:
    return once(
        held, "vocabulary", lambda: compose_vocabulary(checked_inputs(list(inputs)))
    )


class _Layers(Stamped):
    """Layers by the inputs they compose (`_held`)."""


_shared = _Layers()


def _held(packages: tuple[str, ...], page_dir: Path) -> tuple[tuple[Path, ...], dict]:
    """The inputs a selection resolves to, and what is kept of the layer they compose.

    A selection of shared package roots alone, the kernel's and the bundled and
    installed packages', is held for the process, since a plugin update may replace
    the tree under a running server, which keeps answering with the bytes it started
    with. A selection that includes a copy the page holds of a package it selects by
    path is a reading of that page, held in the page's memory (`page_memory`) beside
    the copy's stamp, since the page's next `page init` replaces the copy in place, and
    beside the shared layers, since `forget_layers` replaces those. The layer read
    under either's new stamp replaces the one before it, and goes when the page's
    memory does; a page's server holds that memory for its life
    (`server_rows.RowPublisher`)."""
    inputs = tuple(layer_inputs(packages, page_dir))
    copies = tuple(file_stamp(root) for root in inputs if root.is_relative_to(page_dir))
    if not copies:
        return inputs, _shared.of(inputs, ())
    return inputs, memo(page_dir, _Layers).of(inputs, (_shared, copies))


def forget_layers() -> None:
    """Drop every layer and vocabulary this process holds (`selected_layer`), and the
    Leaf it read itself to be (`running_leaf`), which a layer names as its producer
    (`runtime_selection.forget_tree`). A layer kept in a page's memory was kept beside
    the shared layers this drops (`_held`), so the page's next read composes it again."""
    global _shared
    _shared = _Layers()
    running_leaf.cache_clear()


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
        root / "src/leaf/source/render-checks",
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


def payload_provenance(*, include_path: bool = False, root: Path | None = None) -> dict:
    """Describe the Leaf payload that is running this command, when its source can.

    Beside the commit, one of two dates says how old the payload is: `committed`,
    the commit's committer date, where Git can read it; or `installed`, when a harness
    copied the payload into its plugin cache without `.git`. Both are ISO 8601 with
    an offset. Developer preparations can pass `root` to read another checkout
    through the same provenance rules.
    """
    source = Path(__file__) if root is None else root / "src/leaf/source/layer.py"
    root = PLUGIN_ROOT if root is None else root.resolve()
    provenance: dict = {"path": str(root)} if include_path else {}
    distribution = root / "leaf-distribution.json"
    if distribution.is_file():
        published = json.loads(distribution.read_text())
        provenance.update(published["producer"])
        return provenance
    # Claude Code copies a marketplace plugin without its .git directory into a cache
    # whose final component is the resolved plugin version. Leaf leaves its manifest
    # version unset, so that component is the source commit SHA. Codex's and Pi's
    # copies are clones, which Git reads below. The default root follows this module: a newer
    # sibling cannot change the running copy's identity.
    if installed_copy(root) and not (root / ".git").exists():
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
    if installed_copy(root):
        # Nobody edits a harness's clone, but Codex's lacks what it strips on
        # install, such as the `.agents/skills` link, and adds its own record,
        # which Git would count as changes; and a status costs a hook that asks
        # which Leaf it runs (`other_serving_leaf`) most of its reading.
        provenance["dirty"] = False
        return provenance
    try:
        dirty = subprocess.run(
            [*git, "status", "--porcelain", "--untracked-files=all", "--", "."],
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


def other_serving_leaf(page_dir: Path) -> dict | None:
    """The Leaf the page's running server records (`payload_provenance`), where it is
    another Leaf than the one this process runs (`running_leaf`), or None where no
    server runs or this Leaf started it.

    A server keeps the runtime and layer it started with, so what this process checks
    may not be what the user's tab draws until the server restarts. Another Leaf is
    another install or checkout, or this one at another commit, as a checkout is after
    a commit, or a copy Codex or Pi updated in place is until its server follows the
    update (`server_lifetime.stop_when_service_ends`). Uncommitted edits don't count,
    since the record can't say whether they changed after the server started.
    `leaf server start` restarts such a server under this Leaf
    (`hosting.start_page`), and `page check` notes it
    (`authored_checks.source.source_advice`)."""
    server = running_server(page_dir)
    if server is None:
        return None
    served = server["runtime"]
    here = {"path": str(PLUGIN_ROOT), "commit": running_leaf().get("commit")}
    if all(served.get(key) == value for key, value in here.items()):
        return None
    return served


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
    from leaf.source.registry.layer import merged_registry, stamp_composition

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
    from leaf.source.registry.validation import incoming_registry
    from leaf.source.resource_urls import (
        PUBLIC_MODULES,
        dependency_reference,
        javascript_imports,
    )

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
