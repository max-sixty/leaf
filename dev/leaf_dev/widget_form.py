"""Grade the widgets a short authoring case asked for by how their package defines them.

A Promptfoo `python` assertion. Its `config` names the tags the case asked the author
to write in a package: `drawing`, widgets that draw, and `drawless`, widgets that draw
nothing. It reads the saved page directory with the readers Leaf and `leaf-dev` already
have: the page's markup through `SourceDocument`, each package's declarations and the
module each declared tag has among its `widgets/` (`module_paths`, as the layer
resolves them), and each module's syntax tree (the JavaScript reader Leaf reads
module imports with), so spacing, comments and the name a module imports under don't change a
grade.

Every named tag must be declared by a package the page selects, whose copy it holds
under `packages/`, and placed on the page. A drawing widget passes where its package's module for it calls
`defineWidget`, imported from `/runtime/effect-widget.js` under any name, with the tag,
and no module calls `customElements.define` with it; a drawless one passes where its
package has no module for it and no module defines it either way. Any module that
imports Lit or Leaf's Lit element fails the sample.
"""

from collections.abc import Iterator
from pathlib import Path

from tree_sitter import Node

from leaf.source.registry.contract import module_paths, read_registry_declarations
from leaf.source.registry.storage import layer_packages
from leaf.source.resource_urls import _javascript_reader
from leaf.source.structure import SourceDocument

ADAPTER = "/runtime/effect-widget.js"
OLD_WAY = ("/vendor/lit.js", "/runtime/lib/leaf-element.js")


def nodes(node: Node, kind: str) -> Iterator[Node]:
    """Each node of `kind` under `node`, in source order."""
    for child in node.named_children:
        if child.type == kind:
            yield child
        yield from nodes(child, kind)


def said(node: Node | None) -> str:
    return node.text.decode() if node is not None and node.text is not None else ""


def definitions(module: Path) -> dict[str, set[str]]:
    """The tags a module defines, by how: `component` for a call to the name it imports
    `defineWidget` under, or to `defineWidget` on the namespace it imports the adapter
    as; `plain` for a call to `customElements.define`, on whatever object; and `old` for
    each Lit module it imports, statically or with `import()`."""
    found = {"component": set(), "plain": set(), "old": set()}
    parser, _ = _javascript_reader()
    script = parser.parse(module.read_bytes()).root_node
    adapter = set()
    for statement in nodes(script, "import_statement"):
        specifier = said(statement.child_by_field_name("source"))[1:-1]
        if specifier in OLD_WAY:
            found["old"].add(specifier)
        if specifier == ADAPTER:
            for named in nodes(statement, "import_specifier"):
                if said(named.child_by_field_name("name")) == "defineWidget":
                    alias = named.child_by_field_name("alias")
                    adapter.add(said(alias) if alias else "defineWidget")
            for namespace in nodes(statement, "namespace_import"):
                for name in nodes(namespace, "identifier"):
                    adapter.add(f"{said(name)}.defineWidget")
    for call in nodes(script, "call_expression"):
        function = call.child_by_field_name("function")
        arguments = call.child_by_field_name("arguments")
        values = [
            node
            for node in (arguments.named_children if arguments else [])
            if node.type != "comment"
        ]
        if not values or values[0].type != "string":
            continue
        callee = said(function)
        tag = said(values[0])[1:-1]
        if function is not None and function.type == "import":
            if tag in OLD_WAY:
                found["old"].add(tag)
        elif callee in adapter:
            found["component"].add(tag)
        elif callee == "customElements.define" or callee.endswith(
            ".customElements.define"
        ):
            found["plain"].add(tag)
    return found


def get_assert(output: str, context: dict) -> dict:
    response = context["providerResponse"]
    if response.get("error"):
        return {"pass": False, "score": 0.0, "reason": f"unscored: {response['error']}"}
    page = Path(response["metadata"]["work"]) / "page"
    index = page / "index.html"
    placed = (
        {record["tag"] for record in SourceDocument(index.read_text()).lf_elements}
        if index.is_file()
        else set()
    )
    # The packages the page's layer record selects by path, whose copies it holds, each
    # with its declared tags and the module each has, as the layer resolves them.
    selected = {
        Path(value).name
        for value in layer_packages(page) or []
        if "/" in value or value.startswith((".", "~"))
    }
    packages = {}
    for package in sorted(
        path
        for path in (page / "packages").glob("*")
        if path.is_dir() and path.name in selected
    ):
        declared = read_registry_declarations(package / "registry.json") or {}
        available = {
            f"widgets/{module.name}" for module in package.glob("widgets/*.js")
        }
        packages[package] = (declared, module_paths(declared, available, "widgets"))
    modules = {
        str(path.relative_to(page)): definitions(path)
        for home in [page / "page", *packages]
        for path in sorted(home.glob("widgets/*.js"))
    }
    config = context["config"]
    problems = []
    for tag in [*config.get("drawing", []), *config.get("drawless", [])]:
        if not any(tag in declared for declared, _ in packages.values()):
            problems.append(f"no package declares <{tag}>")
        if tag not in placed:
            problems.append(f"the page places no <{tag}>")
    for tag in config.get("drawing", []):
        # A page's own module for a tag wins over its package's (registry/page.py).
        own = (
            [f"page/widgets/{tag}.js"]
            if (page / "page" / "widgets" / f"{tag}.js").is_file()
            else [
                str((package / paths[tag]).relative_to(page))
                for package, (_, paths) in packages.items()
                if tag in paths
            ]
        )
        if any(name.startswith("page/") for name in own):
            problems.append(
                f"the page's own module, not its package's, defines <{tag}>"
            )
        if not any(tag in modules[name]["component"] for name in own):
            problems.append(
                f"no package module for <{tag}> defines it with defineWidget"
            )
        for name, found in modules.items():
            if tag in found["plain"]:
                problems.append(f"{name} defines <{tag}> with customElements.define")
    for tag in config.get("drawless", []):
        if any(tag in paths for _, paths in packages.values()):
            problems.append(f"a package has a module for <{tag}>, which draws nothing")
        for name, found in modules.items():
            if tag in found["component"] | found["plain"]:
                problems.append(f"{name} defines <{tag}>, which draws nothing")
    for name, found in modules.items():
        for specifier in sorted(found["old"]):
            problems.append(f"{name} imports {specifier}")
    passed = not problems
    return {
        "pass": passed,
        "score": float(passed),
        "reason": "; ".join(problems) or "each widget is written the one way",
        "metadata": {
            "widget_form": {
                "placed": sorted(placed),
                "packages": {
                    str(package.relative_to(page)): sorted(declared)
                    for package, (declared, _) in packages.items()
                },
                "problems": problems,
            }
        },
    }
