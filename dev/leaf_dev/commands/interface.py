"""Print the package interface: every name a package's author can lean on Leaf for,
with its form and what uses it.

    uv run leaf-dev interface [--json] [--base [REF]]

Each part is read from the list that defines it, as the check that guards it reads it:

- Declaration keys: `$keys` in `browser/registry.json`, an element declaration's
  keys, which `test_the_key_docs_hold_to_the_keys_their_schema_admits` holds to
  `schema.DECLARATION_SCHEMA`. `description` is among them: every declaration carries
  it, and `$keys` gives its meaning in the table's own opening entry. A key's form is
  the attribute Leaf paints it as for a stylesheet, where the kernel registry's
  `$marks` paints one, and Leaf's own elements that carry it.
- Leaf's elements: the tags `browser/registry.json` declares (`is_element_name`); the
  other keys there are selector idioms, whose classes are styling names. An element's
  form is the facts its declaration states.
- The widget protocol: what Leaf sets on an element, hears from it and reads off it.
  Code keeps only its events: those Leaf's runtime listens for or makes (`events`)
  that the library exports by name, as `lib/widget-events.js` does. A mark is any
  `data-lf-…` name a reference gives in code, since that shape says what it is, and
  each attribute the kernel registry's `$marks` paints for a declaration key. A focus
  mark's shadow part, its name less `data-` (`module-input.md`), is the mark's twin,
  so the census lists the mark alone, with the mark's own uses. The members and the
  other events are read from the protocol's index, the part of `module-widgets.md`
  before its first section: each entry's lead name, and each name it gives in code of
  a member of the element or its class (`lf` then a capital, `static name`, or
  `name()` where no function has that name), or of an event Leaf's runtime listens for
  or makes. A lead named by a registry field, as `record.property` is, belongs to the
  declaration key `verbs`. For members and events the census reads no other
  reference, and `dev/tests/model/test_interface.py` holds the index to the ones the
  other references give.
- Modules: the paths `$public-modules` in the kernel registry admits outside the
  library (`/runtime/lib/`): Leaf's own modules under `/runtime/`, such as
  `widget-api.js` and `effect-widget.js`, and the dependencies Leaf serves under
  `/vendor/`, such as Lit's. A module's form says which of the two it is.
- Functions: the exports of Leaf's own modules, `export *` followed, as
  `tests/runtime/widget-api.test.mjs` reads `widget-api.js`'s. A function's form is the
  section the references' index (`module-authoring.md`, "Functions") files it under, or
  else the module that exports it, with `portable` where `portable-api.js` exports it.
- Vendored exports: the names the vendored modules export, which Leaf's build
  chooses (`build/vendor.mjs`). A name's form is the module that exports it.
- Data contracts: the names `$data.contracts` declares in `browser/registry.json` and
  in each bundled package's registry. An example page's registry declares contracts for
  that page alone, which are no part of the interface. A contract's form is the
  package that declares it and how widgets bind it: as an `output`, or as an input by
  `reference` to another widget or by `source` to data the agent sets. A contract
  states the invoker commands its producer takes in the prose of its `producer`
  instructions, so the census lists no command.
- Styling names: the custom properties the references name, and the classes Leaf's
  sheets style that the references or a kernel idiom name (`leaf_dev.styling_names`,
  which `tests/model/test_theme_tokens.py` reads). A name's form is the side of the
  package boundary that sets it, where the tree settles it. A name the theme's tokens
  (`browser/styles/tokens.css`) set is the theme's, whoever else sets it, since a
  theme or page restates such a name. Otherwise a name only Leaf's other sheets and
  code set is Leaf's, and a name a package or page sets is the package's, even where
  Leaf's own boxes set it too, unless a package also reads it. The library runs inside
  a package's module, so it counts with the packages. A name that both sides set and
  a package reads, or that nothing sets, is `unsorted`. A property is set by a
  declaration, `@property` or `setProperty`, and read anywhere else, as by `var()`, a
  style query or a helper handed its name: `dom/root-headers.js` hands
  `--lf-root-headers` to `setRuntimeRootStyle`, so nothing reads as setting it. A
  class is read where a `.` leads it and set, as by a `class` attribute, elsewhere,
  but a whole string naming an event the script makes, hears or exports is the
  event, as `"lf-preview"` is in `new CustomEvent("lf-preview")`.
- Parts: the parts of Leaf's chrome a theme restyles, as `package-themes.md`'s "Leaf's
  chrome" table lists them and `tests/browser/threads/test_layout.py` reads them. A
  widget's own `part` names are its package's, for a page to style with `::part`
  (`packages.md`, "Styles and composition"), so the census reads none of them.

The census counts a name as an author imports it or writes it as a key. A function's
options, an event's `detail` and an element's attributes are fields of that name's
contract, which its module or reference describes, so `--base` reports none of them
and a change to one is read in its diff.

A name's users are counted in three groups: the bundled packages (`packages/*`), the
library's modules (`browser/runtime/lib/`), and the example pages (`examples/`, a page
being its HTML file, its `.page` directory and its earlier versions). The counts leave
out Leaf's own registry, whose elements a key's form names instead. A use is:

- for a key, an element declaration in a registry that carries it;
- for a contract, an element declaration in a registry whose `inputs` or `outputs`
  name it;
- for an element, its start tag;
- for a module, a script's import or re-export of it, or its `import("…")`, under the
  path `$public-modules` spells;
- for a function or a vendored export, a script's import of it by name from a module
  that exports it;
- for a protocol member, a script's property of its name; for an event, a call in a
  script that listens for or makes it (`Tree.events`); for a mark, its name, or its
  `dataset` property, in a file's code less its comments;
- for a styling name, its name in a file's code less its comments;
- for a part, an attribute selector naming it (`[part~="card"]`), in a file's code
  less its comments.

An event named by a common word, as `change` is, counts every listener for it, a
media query's included. A script that imports a library module using a name reaches
the name through it, as a `LeafElement` subclass reaches `lf-action` through
`record()`. Importing a module is no use of each name in it, so such users print as a
second count after a `+`, and each part lists the names with the fewest direct users
first.

`--base [REF]` prints instead the names this tree adds and removes against REF, the
merge base with `main` without one, part by part, for a pull request to carry. An
export counts once for each module it is exported from, so making an existing
function portable adds it from `portable-api.js`.
`--json` prints the same facts as one document, with the commit the working tree
stands on. The command reports; no test or job reads its counts.
"""

import json
import os
import re
import tempfile
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import cache, cached_property
from pathlib import Path

import click
import tree_sitter_javascript
import turbohtml
from markdown_it import MarkdownIt
from tree_sitter import Language, Node, Parser, Query, QueryCursor

from leaf.source.registry.contract import element_declarations, is_element_name
from leaf.source.resource_urls import javascript_imports
from leaf_dev import ROOT
from leaf_dev.arms import (
    arm_commit,
    base_option,
    copy_committed,
    merge_base,
    working_files,
)
from leaf_dev.styling_names import (
    CLASS,
    NAME,
    REFERENCES,
    code,
    documented,
    idioms,
    leaf_names,
    public_names,
)

# What each reading reads, at one version of Leaf.
PATHS = ("browser", "packages", "examples", REFERENCES, "src/leaf")
PARTS = {
    "keys": "Declaration keys",
    "elements": "Leaf's elements",
    "protocol": "The widget protocol",
    "contracts": "Data contracts",
    "modules": "Modules",
    "functions": "Functions",
    "vendored": "Vendored exports",
    "parts": "Parts",
    "styling": "Styling names",
}
GROUPS = ("packages", "library", "examples")
SCRIPTS = (".js", ".mjs", ".html")
CODE = {".css", ".py", *SCRIPTS}
LIBRARY = "browser/runtime/lib/"
KERNEL = "browser/runtime/kernel-registry.json"
THEME = "browser/styles/tokens.css"
# The calls whose first argument names an event: listening for one, or making one, as
# an `Event` subclass's constructor does through `super`.
EVENT_CLASSES = {"Event", "CustomEvent", "ErrorEvent"}
EVENT_CALLS = {"addEventListener", "super", *EVENT_CLASSES}
# A run of class names, or of the template substitutions between them, that a
# string or a `class` attribute holds.
CLASS_RUN = r"(?:[\w\s-]|\$\{[^}]*\})*"
# The functions whose first parameter a call's first argument stands in for.
FUNCTIONS = {
    "method_definition",
    "function_declaration",
    "function_expression",
    "arrow_function",
}
LANGUAGE = Language(tree_sitter_javascript.language())
# Each call's first argument, a string or a name, and the function it calls.
CALLS = Query(
    LANGUAGE,
    """
    (call_expression
      function: [(identifier) (super)
                 (member_expression
                   property: [(property_identifier) (private_property_identifier)])]
        @callee
      arguments: (arguments . [(string (string_fragment) @string) (identifier) @named]))
    (new_expression
      constructor: (identifier) @callee
      arguments: (arguments . [(string (string_fragment) @string) (identifier) @named]))
    """,
)
CONSTANTS = Query(
    LANGUAGE,
    """
    (export_statement
      declaration: (lexical_declaration
        (variable_declarator
          name: (identifier) @name value: (string (string_fragment) @value))))
    """,
)
MARK = re.compile(r"(?<![\w-])data-lf-[a-z0-9]+(?:-[a-z0-9]+)*")
MARKDOWN = MarkdownIt("commonmark").enable("table")
PROPERTIES = Query(
    LANGUAGE, "[(property_identifier) (shorthand_property_identifier)] @property"
)


def spans(text: str) -> list[str]:
    """The code a Markdown text gives inline, outside its code blocks."""
    return [
        " ".join(child.content.split())
        for token in MARKDOWN.parse(text)
        if token.type == "inline"
        for child in token.children or ()
        if child.type == "code_inline"
    ]


def said(node: Node | None) -> str:
    """A syntax node's source text; the grammar gives every node read here."""
    assert node is not None and node.text is not None
    return node.text.decode()


@cache
def scripts(file: Path) -> tuple[Node, ...]:
    """A module's syntax tree, or each of an HTML page's scripts'."""
    text = file.read_text(encoding="utf-8")
    sources = (
        [text]
        if file.suffix != ".html"
        else [each.text for each in turbohtml.parse(text).select("script")]
    )
    parser = Parser(LANGUAGE)
    return tuple(parser.parse(each.encode()).root_node for each in sources)


@cache
def properties(file: Path) -> frozenset[str]:
    """Every property a file's scripts name, defined or read."""
    return frozenset(
        said(node)
        for script in scripts(file)
        for nodes in QueryCursor(PROPERTIES).captures(script).values()
        for node in nodes
    )


def called(callee: Node) -> tuple[str, bool]:
    """The name of the function a call calls, and whether the call is to the script's
    own function: a bare name, or a method of `this` (`#send` for `this.#send(…)`)."""
    receiver = callee.child_by_field_name("object")
    name = callee.child_by_field_name("property") or callee
    return said(name), receiver is None or receiver.type == "this"


def makes_events(node: Node) -> bool:
    """Whether a `super(…)` call stands in an `Event` subclass, whose constructor makes
    the event its first argument names."""
    around = node.parent
    while around is not None and around.type not in {"class_declaration", "class"}:
        around = around.parent
    heritage = around and next(
        (child for child in around.named_children if child.type == "class_heritage"),
        None,
    )
    return bool(heritage) and said(heritage).split()[-1] in EVENT_CLASSES


def enclosing(node: Node) -> Node | None:
    """The function a node stands in."""
    around = node.parent
    while around is not None and around.type not in FUNCTIONS:
        around = around.parent
    return around


def first(function: Node) -> str:
    """A function's first parameter's name, or `""`."""
    parameters = function.child_by_field_name("parameters")
    head = parameters.named_children[:1] if parameters else []
    return said(head[0]) if head and head[0].type == "identifier" else ""


def defined(function: Node) -> str:
    """The name a function is defined under, or `""` for an unnamed one."""
    name = function.child_by_field_name("name")
    if (
        name is None
        and function.parent
        and function.parent.type == "variable_declarator"
    ):
        name = function.parent.child_by_field_name("name")
    return said(name) if name else ""


cached_code = cache(code)


def matches(query: Query, script: Node) -> Iterator[dict[str, str]]:
    """A query's matches in a script, each capture's text by its name."""
    for _, match in QueryCursor(query).matches(script):
        yield {capture: said(nodes[0]) for capture, nodes in match.items()}


def descendants(node: Node, kind: str) -> Iterator[Node]:
    for child in node.named_children:
        if child.type == kind:
            yield child
        yield from descendants(child, kind)


def imports(script: Node) -> Iterator[tuple[str, Node]]:
    """Each import's specifier and statement."""
    for node in script.named_children:
        if node.type == "import_statement":
            yield said(node.child_by_field_name("source"))[1:-1], node


@dataclass
class Name:
    """One name of the interface: its form, and by group the files of each of its
    users, and of each user that only imports a library module using it. An export
    also names the modules it is exported from, and a styling name says which sides
    set and read it."""

    form: str = ""
    homes: list[str] = field(default_factory=list)
    users: dict[str, defaultdict[str, list[str]]] = field(
        default_factory=lambda: {group: defaultdict(list) for group in GROUPS}
    )
    through: dict[str, defaultdict[str, list[str]]] = field(
        default_factory=lambda: {group: defaultdict(list) for group in GROUPS}
    )
    sets: set[str] = field(default_factory=set)
    reads: set[str] = field(default_factory=set)

    def used(self, user: tuple[str, str], where: str) -> None:
        group, who = user
        if where not in self.users[group][who]:
            self.users[group][who].append(where)

    def count(self, group: str) -> int:
        return len(self.users[group])

    def reached(self, group: str) -> int:
        """The users in `group` that reach the name only through the library."""
        return len(self.through[group].keys() - self.users[group].keys())


class Tree:
    """The files of `PATHS` at one version: the working tree's tracked and unignored
    files, or a commit's, extracted under `root`."""

    def __init__(self, root: Path, files: list[str]):
        self.root = root
        self.files = sorted(files)

    @classmethod
    def working(cls) -> "Tree":
        return cls(ROOT, working_files(PATHS))

    @classmethod
    def at(cls, ref: str, scratch: Path) -> "Tree":
        copy_committed(PATHS, scratch, ref)
        files = [path for path in scratch.rglob("*") if path.is_file()]
        return cls(scratch, [str(path.relative_to(scratch)) for path in files])

    def text(self, path: str) -> str:
        return (self.root / path).read_text(encoding="utf-8")

    def json(self, path: str) -> dict:
        return json.loads(self.text(path))

    def code(self, path: str) -> str:
        return cached_code(self.root / path)

    def scripts(self, path: str) -> tuple[Node, ...]:
        return scripts(self.root / path)

    def properties(self, path: str) -> frozenset[str]:
        return properties(self.root / path) if path.endswith(SCRIPTS) else frozenset()

    def exported(self, path: str) -> dict[str, str]:
        """The string constants a file's scripts export, by name."""
        return {
            match["name"]: match["value"]
            for script in self.scripts(path)
            for match in matches(CONSTANTS, script)
        }

    def runtime_strings(self, within: str) -> dict[str, str]:
        """The strings the runtime's modules under `within` export, by name."""
        return {
            name: value
            for path in self.files
            if path.startswith(within) and path.endswith(".js")
            for name, value in self.exported(path).items()
        }

    @cached_property
    def constants(self) -> dict[str, str]:
        """The strings the runtime's modules export, by name, among them the events
        they make or hear (`PAGE_INTERFACE` in `readings/presentation.js`) and those the library
        hands a widget to dispatch (`lib/widget-events.js`)."""
        return self.runtime_strings("browser/runtime/")

    def events(self, path: str) -> set[str]:
        """The events a file's scripts listen for or make: each event call's first
        argument, a string or the runtime's constant naming one, and each string handed
        to a function of the script's own that hands its first parameter to an event
        call, as `LeafElement.record` hands `"lf-action"` to `#send`."""
        if not path.endswith(SCRIPTS):
            return set()
        found = set()
        for script in self.scripts(path):
            wrappers, handed = set(), []
            for _, match in QueryCursor(CALLS).matches(script):
                callee, own = called(node := match["callee"][0])
                if callee == "super" and not makes_events(node):
                    continue
                if "string" in match:
                    handed.append((callee, own, said(match["string"][0])))
                elif callee in EVENT_CALLS:
                    named = said(match["named"][0])
                    if named in self.constants:
                        found.add(self.constants[named])
                    elif (function := enclosing(match["named"][0])) and named == first(
                        function
                    ):
                        wrappers.add(defined(function))
            wrappers.discard("")
            found |= {
                each
                for callee, own, each in handed
                if callee in EVENT_CALLS or (own and callee in wrappers)
            }
        return found

    @cached_property
    def heard(self) -> set[str]:
        """The events Leaf's runtime listens for or makes."""
        return set().union(
            *(
                self.events(path)
                for path in self.files
                if path.startswith("browser/runtime/") and path.endswith(".js")
            )
        )

    @cached_property
    def users(self) -> dict[str, tuple[str, str]]:
        """Each file a use is read in, with the group and the user it counts for: a
        bundled package, a library module, or an example page, whose earlier versions
        (`versions/<stem>.vN.html`) are the page's too."""
        found = {}
        for path in self.files:
            parts = path.split("/")
            if "vendor" in parts:
                continue
            if parts[0] == "packages" and len(parts) > 2:
                found[path] = ("packages", parts[1])
            elif path.startswith(LIBRARY):
                found[path] = ("library", parts[-1])
            elif page := re.match(
                r"examples/(.*?)(?:versions/)?([^/]+?)(?:\.v\d+)?\.(?:html|page)(?:/|$)",
                path,
            ):
                found[path] = ("examples", page[1] + page[2])
        return found

    def code_users(self) -> Iterator[tuple[str, tuple[str, str]]]:
        """The files whose code a use is read in, each with its group and user."""
        for path, user in self.users.items():
            if Path(path).suffix in CODE:
                yield path, user

    def declarations(self) -> Iterator[tuple[str, tuple[str, str], str, dict]]:
        """Each element declaration in a user's registry, with the registry's path, the
        user it counts for, and its tag."""
        for path, user in self.users.items():
            if path.endswith("registry.json"):
                for tag, declaration in element_declarations(self.json(path)).items():
                    yield path, user, tag, declaration

    def specifiers(self, path: str) -> set[str]:
        """The paths a script imports, re-exports or loads by `import("…")`, each as
        the script spells it."""
        return {
            specifier
            for script in self.scripts(path)
            for _, _, specifier in javascript_imports(said(script).encode(), path, [])
        }

    @cached_property
    def painted(self) -> dict[str, str]:
        """The attribute the kernel registry's `$marks` paints for each declaration key.
        The table opens with its own description, which paints nothing."""
        return {
            key: mark["attribute"]
            for key, mark in self.json(KERNEL)["$marks"].items()
            if key != "description"
        }

    @cached_property
    def public_modules(self) -> list[str]:
        """The module paths `$public-modules` admits outside the library."""
        return [
            path
            for path in self.json(KERNEL)["$public-modules"]["paths"]
            if not path.startswith("/runtime/lib/")
        ]

    def imported_modules(self, path: str) -> set[str]:
        """The library modules a script imports, by file name."""
        return {
            os.path.basename(specifier)
            for script in self.scripts(path)
            for specifier, _ in imports(script)
            if specifier.startswith("/runtime/lib/")
        }


def keys(tree: Tree) -> dict[str, Name]:
    core = tree.json("browser/registry.json")
    rows = {}
    for key in core["$keys"]:
        own = [tag for tag in sorted(core) if is_element_name(tag) and key in core[tag]]
        form = [f"painted {tree.painted[key]}"] if key in tree.painted else []
        rows[key] = Name(
            "; ".join(form + ([f"Leaf's {', '.join(own)}"] if own else []))
        )
    for path, user, tag, declaration in tree.declarations():
        for key in declaration.keys() & rows.keys():
            rows[key].used(user, f"{path}: {tag}")
    return rows


def contracts(tree: Tree) -> dict[str, Name]:
    registries = {"browser/registry.json": "Leaf"} | {
        path: who
        for path, (group, who) in tree.users.items()
        if group == "packages" and path == f"packages/{who}/registry.json"
    }
    declared = defaultdict(list)
    for path, who in sorted(registries.items()):
        for name in tree.json(path).get("$data", {}).get("contracts", {}):
            declared[name].append(who)
    rows = {name: Name() for name in declared}
    bound = defaultdict(set)
    for path, user, tag, declaration in tree.declarations():
        for kinds, binding in [
            *(({"output"}, each) for each in declaration.get("outputs", {}).values()),
            *(
                (each.keys() & {"reference", "source"}, each)
                for each in declaration.get("inputs", {}).values()
            ),
        ]:
            if (row := rows.get(name := binding["contract"])) is not None:
                bound[name] |= kinds
                row.used(user, f"{path}: {tag}")
    for name, who in declared.items():
        declares = "declares" if len(who) == 1 else "declare"
        kinds = ", ".join(sorted(bound[name])) or "no widget binds it"
        rows[name].form = f"{', '.join(who)} {declares} it; {kinds}"
    return rows


def elements(tree: Tree) -> dict[str, Name]:
    rows = {
        tag: Name(", ".join(sorted(declaration.keys() - {"description"})))
        for tag, declaration in tree.json("browser/registry.json").items()
        if is_element_name(tag)
    }
    for path, user in tree.code_users():
        for tag, row in rows.items():
            if re.search(rf"<{tag}(?![\w-])", tree.code(path)):
                row.used(user, path)
    return rows


def protocol(tree: Tree, functions: dict[str, Name]) -> dict[str, Name]:
    index = tree.text(f"{REFERENCES}/module-widgets.md").split("\n## ", 1)[0]
    leads = set(re.findall(r"^- \*\*`([^`]+)`", index, re.M))
    # The events Leaf hears or makes that the library exports by name are the
    # protocol's whether or not the index names them.
    library = set(tree.runtime_strings(LIBRARY).values())
    rows = {name: Name("event") for name in tree.heard & library}
    for path in tree.files:
        if path.startswith(f"{REFERENCES}/") and path.endswith(".md"):
            for span in spans(tree.text(path)):
                rows |= {name: Name("mark") for name in MARK.findall(span)}
    rows |= {name: Name("mark") for name in tree.painted.values()}
    for span in spans(index):
        name = re.sub(r"^static |\(\)$|=.*$", "", span)
        if "." in name or name.startswith("data-lf-"):
            continue
        if name in tree.heard:
            rows[name] = Name("event")
        elif (
            span in leads
            or span.startswith("static ")
            or (span.endswith("()") and name not in functions)
            or re.fullmatch(r"lf[A-Z]\w*", name)
        ):
            rows[name] = Name("member")
    marks = {}
    for name, row in rows.items():
        if row.form == "mark":
            head, *rest = name.removeprefix("data-").split("-")
            dataset = f"dataset\\.{head}{''.join(map(str.title, rest))}"
            marks[name] = re.compile(
                rf"(?<![\w$-])(?:{re.escape(name)}|{dataset})(?![\w$-])"
            )
    for path, user in tree.code_users():
        events, held = tree.events(path), tree.properties(path)
        for name, row in rows.items():
            if (
                marks[name].search(tree.code(path))
                if row.form == "mark"
                else name in (events if row.form == "event" else held)
            ):
                row.used(user, path)
    return rows


def exports(tree: Tree, path: str) -> set[str]:
    """A module's exports, each `export *` read through to the module it names."""
    names = set()
    for node in tree.scripts(path)[0].named_children:
        if node.type != "export_statement":
            continue
        declaration = node.child_by_field_name("declaration")
        specifiers = list(descendants(node, "export_specifier"))
        for specifier in specifiers:
            alias = specifier.child_by_field_name("alias")
            names.add(said(alias or specifier.child_by_field_name("name")))
        if declaration is not None:
            for named in [declaration, *declaration.named_children]:
                if (name := named.child_by_field_name("name")) is not None:
                    names.add(said(name))
        elif not specifiers:
            source = said(node.child_by_field_name("source"))[1:-1]
            names |= exports(tree, os.path.normpath(Path(path).parent / source))
    return names


def function_index(tree: Tree) -> dict[str, str]:
    """The section `module-authoring.md`, "Functions", files each function under."""
    text = tree.text(f"{REFERENCES}/module-authoring.md")
    start = text.index("\n### Functions\n")
    index = text[start : text.index("\n### ", start + 1)]
    sections = {}
    reference = "module-authoring.md"
    for part in re.split(r"\n\n+", index):
        if heading := re.match(r"In \[(module-[a-z-]+\.md)\]|In this file", part):
            reference = heading[1] or "module-authoring.md"
        for item in re.split(r"\n(?=- )", part):
            if entry := re.match(r'- "([^"]+)": (.*)', " ".join(item.split())):
                for name in re.findall(r"`([A-Za-z_$][\w$]*)`", entry[2]):
                    sections[name] = f'{reference}, "{entry[1]}"'
    return sections


def modules(tree: Tree) -> dict[str, Name]:
    rows = {
        path: Name("Leaf's" if path.startswith("/runtime/") else "vendored")
        for path in tree.public_modules
    }
    for path, user in tree.code_users():
        if path.endswith(SCRIPTS):
            for module in tree.specifiers(path) & rows.keys():
                rows[module].used(user, path)
    return rows


def named_exports(
    tree: Tree, modules: list[str], index: dict[str, str]
) -> dict[str, Name]:
    """The names `modules` export, each with the section `index` files it under, or
    else the modules that export it, as its form, and its imports from them as uses."""
    homes = defaultdict(list)
    for module in modules:
        for name in exports(tree, f"browser{module}"):
            homes[name].append(module)
    rows = {
        name: Name(
            ("portable; " if "/runtime/portable-api.js" in where else "")
            + index.get(name, ", ".join(map(os.path.basename, where))),
            where,
        )
        for name, where in homes.items()
    }
    for path, user in tree.code_users():
        if not path.endswith(SCRIPTS):
            continue
        imported = {
            said(specifier.child_by_field_name("name"))
            for script in tree.scripts(path)
            for module, node in imports(script)
            if module in modules
            for specifier in descendants(node, "import_specifier")
        }
        for name in imported & rows.keys():
            rows[name].used(user, path)
    return rows


def functions(tree: Tree) -> dict[str, Name]:
    own = [path for path in tree.public_modules if path.startswith("/runtime/")]
    return named_exports(tree, own, function_index(tree))


def vendored(tree: Tree) -> dict[str, Name]:
    others = [path for path in tree.public_modules if not path.startswith("/runtime/")]
    return named_exports(tree, others, {})


def parts(tree: Tree) -> dict[str, Name]:
    themes = tree.text(f"{REFERENCES}/package-themes.md")
    chrome = themes.split("\n## Leaf's chrome", 1)[1].split("\n## ", 1)[0]
    rows = {
        name: Name("Leaf's chrome")
        for name in re.findall(r"^\| `([a-z-]+)` ", chrome, re.M)
    }
    for path, user in tree.code_users():
        for name, row in rows.items():
            selector = rf"\[\s*part\s*[~|]?=\s*[\"']?{re.escape(name)}[\"'\s\]]"
            if re.search(selector, tree.code(path)):
                row.used(user, path)
    return rows


def styling(tree: Tree) -> dict[str, Name]:
    root = tree.root
    authored = idioms(root)
    classes = leaf_names(root)[1] & public_names(root)
    rows = {name: Name() for name in documented(root) | classes}
    for path in tree.files:
        if Path(path).suffix not in CODE or "vendor" in path.split("/"):
            continue
        # The library runs inside a package's module, so it sets and reads as one.
        if path in tree.users:
            side = tree.users[path][0].replace("library", "packages")
        elif path == THEME:
            side = "theme"
        elif path.startswith(("browser/", "src/leaf/")):
            side = "Leaf"
        else:
            continue
        # A whole string naming an event the script makes, hears or exports is the
        # event, not a class: a quote stands on each side of it.
        events = tree.events(path) | (set(tree.exported(path).values()) & tree.heard)
        text = tree.code(path)
        for pattern in (NAME, CLASS):
            for found in pattern.finditer(text):
                if (row := rows.get(name := found[0])) is None:
                    continue
                before, after = text[: found.start()], text[found.end() :]
                if pattern is NAME:
                    sets = bool(
                        re.search(r"@property\s+$", before)
                        or re.search(r"(set|remove)Property\(\s*[\"'`]$", before)
                        or (
                            re.match(r"[\"'`]?\s*:", after)
                            and not re.search(r"style\(\s*$", before)
                        )
                    )
                elif before.endswith("."):
                    sets = False
                # A class is set where a string or `class` attribute lists it, and
                # a word in a sentence is no use of it.
                elif not (
                    re.search(rf"[\"'`]{CLASS_RUN}$", before[-200:])
                    and re.match(rf"{CLASS_RUN}[\"'`]", after)
                ) or (
                    name in events
                    and before[-1:] in {'"', "'", "`"}
                    and after[:1] == before[-1:]
                ):
                    continue
                else:
                    sets = True
                (row.sets if sets else row.reads).add(side)
                if path in tree.users:
                    row.used(tree.users[path], path)
    outside = {"packages", "examples"}
    for name, row in rows.items():
        if name in authored:
            row.form = "a page writes it"
        elif "theme" in row.sets:
            row.form = "the theme sets it"
        elif "Leaf" in row.sets and not row.sets & outside:
            row.form = "Leaf sets it"
        # A name a package sets crosses to Leaf, though Leaf's own boxes set it too,
        # unless a package reads it as well.
        elif row.sets & outside and not ("Leaf" in row.sets and row.reads & outside):
            row.form = "a package sets it"
        else:
            row.form = "unsorted"
    return rows


def census(tree: Tree) -> dict[str, dict[str, Name]]:
    """Every part's names, each with its form and users, fewest direct users first. A
    script that imports a library module using a name reaches the name through it."""
    read = {
        "keys": keys(tree),
        "elements": elements(tree),
        "contracts": contracts(tree),
        "modules": modules(tree),
    }
    read["functions"] = functions(tree)
    read["vendored"] = vendored(tree)
    read["parts"] = parts(tree)
    read["protocol"] = protocol(tree, read["functions"])
    read["styling"] = styling(tree)
    imported = {
        path: (user, tree.imported_modules(path))
        for path, user in tree.code_users()
        if user[0] != "library" and path.endswith(SCRIPTS)
    }
    for rows in read.values():
        for row in rows.values():
            for path, ((group, who), library) in imported.items():
                if via := library & row.users["library"].keys():
                    row.through[group][who].append(f"{path}: {', '.join(sorted(via))}")
    return {
        part: dict(
            sorted(
                read[part].items(),
                key=lambda item: (*map(item[1].count, GROUPS), item[0].lower()),
            )
        )
        for part in PARTS
    }


def change(rows: dict[str, Name], against: dict[str, Name]) -> dict[str, list[str]]:
    """The names `rows` holds that `against` lacks, each with the modules it newly comes
    from where it is an export."""
    entries = [
        {(name, home) for name, row in each.items() for home in row.homes or [""]}
        for each in (rows, against)
    ]
    found = defaultdict(list)
    for name, home in sorted(entries[0] - entries[1]):
        found[name] += [home] if home else []
    return dict(found)


def listed(names: dict[str, list[str]]) -> str:
    """Names a comparison found, an export's under each module it comes from."""
    grouped = defaultdict(list)
    for name, homes in names.items():
        for home in homes or [""]:
            grouped[home].append(f"`{name}`")
    return "; ".join(
        (f"from `{home}` " if home else "") + ", ".join(each)
        for home, each in grouped.items()
    )


def document(parts: dict[str, dict[str, Name]]) -> dict:
    return {
        part: [
            {
                "name": name,
                "form": row.form,
                **(
                    {"sets": sorted(row.sets), "reads": sorted(row.reads)}
                    if part == "styling"
                    else {}
                ),
                "users": {group: dict(row.users[group]) for group in GROUPS},
                "through_library": {
                    group: dict(row.through[group])
                    for group in GROUPS
                    if row.through[group]
                },
            }
            for name, row in rows.items()
        ]
        for part, rows in parts.items()
    }


def printed(parts: dict[str, dict[str, Name]]) -> str:
    lines = []
    for part, rows in parts.items():
        width = max(map(len, rows), default=0)
        lines += [
            f"{PARTS[part]}: {len(rows)}",
            f"  {'':{width}}   pkgs   lib     ex  form",
        ]
        for name, row in rows.items():
            # A count, and after a `+` the users that reach the name only through
            # the library.
            packages, library, examples = (
                f"{row.count(group)}"
                + (f"+{extra}" if (extra := row.reached(group)) else "")
                for group in GROUPS
            )
            # The packages that use a name, where there are few.
            few = sorted(row.users["packages"])
            form = " ".join(
                filter(
                    None, [row.form, f"[{', '.join(few)}]" if 0 < len(few) <= 2 else ""]
                )
            )
            if part == "styling":
                form += f" (sets: {', '.join(sorted(row.sets)) or '-'};"
                form += f" reads: {', '.join(sorted(row.reads)) or '-'})"
            lines.append(
                f"  {name:{width}}  {packages:>5}  {library:>4}  {examples:>5}  {form}".rstrip()
            )
        lines.append("")
    return "\n".join(lines)


@click.command()
@click.option("--json", "as_json", is_flag=True, help="Print one JSON document.")
@base_option()
def interface(as_json: bool, base: str | None) -> None:
    """Print every name a package's author can lean on Leaf for: an element
    declaration's keys, Leaf's elements, the widget protocol, data contracts, modules,
    functions, vendored exports, parts and styling names, each with its form and what
    uses it. With --base, print the names this tree adds and removes."""
    head = census(Tree.working())
    if base is None:
        click.echo(
            json.dumps({"head": arm_commit(None), "parts": document(head)}, indent=1)
            if as_json
            else printed(head)
        )
        return
    commit = arm_commit(base or merge_base())
    with tempfile.TemporaryDirectory() as scratch:
        earlier = census(Tree.at(commit, Path(scratch)))
    added = {part: change(head[part], earlier[part]) for part in PARTS}
    removed = {part: change(earlier[part], head[part]) for part in PARTS}
    if as_json:
        click.echo(
            json.dumps({"base": commit, "added": added, "removed": removed}, indent=1)
        )
        return
    lines = [
        f"{PARTS[part]}: "
        + "; ".join(
            f"{verb} {listed(names[part])}"
            for verb, names in (("adds", added), ("removes", removed))
            if names[part]
        )
        for part in PARTS
        if added[part] or removed[part]
    ]
    click.echo(
        "\n".join([f"Against {commit[:10]}:", *lines])
        if lines
        else f"No name added or removed against {commit[:10]}."
    )
