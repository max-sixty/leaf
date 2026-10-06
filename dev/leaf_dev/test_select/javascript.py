"""JavaScript definition/reference metadata from Leaf's existing syntax reader.

Only top-level declarations and literal module bindings form source witnesses.
Identifier references are an overapproximation, never an exclusion proof. No
JavaScript executes, and this query needs no Node subprocess or npm installation.
"""

from leaf.revision_artifact import javascript_tree


def walk(node):
    pending = [node]
    while pending:
        current = pending.pop()
        yield current
        pending.extend(reversed(current.named_children))


def javascript_records(source: str, path: str) -> dict:
    data = source.encode()
    tree = javascript_tree(data, path)
    definitions, imports, unresolved = {}, [], []

    def text(node):
        return data[node.start_byte : node.end_byte].decode()

    for raw in tree.root_node.named_children:
        node = (
            raw.child_by_field_name("declaration")
            if raw.type == "export_statement"
            else raw
        )
        if node is None:
            continue
        if node.type in {"lexical_declaration", "variable_declaration"}:
            targets = node.named_children
        elif node.type in {
            "function_declaration",
            "generator_function_declaration",
            "class_declaration",
        }:
            targets = [node]
        else:
            targets = []
        for target in targets:
            name_node = target.child_by_field_name("name")
            if name_node is None or name_node.type != "identifier":
                continue
            name = text(name_node)
            refs = {
                text(child)
                for child in walk(target)
                if child.type
                in {
                    "identifier",
                    "property_identifier",
                    "shorthand_property_identifier",
                }
            }
            definitions[name] = {
                "start": raw.start_point[0] + 1,
                "end": raw.end_point[0] + 1,
                "code": text(raw),
                "refs": sorted(refs - {name}),
            }
        if node.type != "import_statement":
            continue
        literal = node.child_by_field_name("source")
        if any(child.type != "string_fragment" for child in literal.named_children):
            unresolved.append(
                {"line": node.start_point[0] + 1, "reason": "escaped module specifier"}
            )
            continue
        names = []
        for clause in (
            child for child in node.named_children if child.type == "import_clause"
        ):
            for binding in clause.named_children:
                if binding.type == "identifier":
                    names.append({"local": text(binding), "remote": "default"})
                elif binding.type == "namespace_import":
                    names.append(
                        {"local": text(binding.named_children[-1]), "remote": "*"}
                    )
                elif binding.type == "named_imports":
                    for specifier in binding.named_children:
                        imported = specifier.child_by_field_name("name")
                        local = specifier.child_by_field_name("alias") or imported
                        names.append({"local": text(local), "remote": text(imported)})
        imports.append({"source": text(literal)[1:-1], "names": names})
    return {
        "definitions": definitions,
        "imports": imports,
        "unresolved_imports": unresolved,
    }
