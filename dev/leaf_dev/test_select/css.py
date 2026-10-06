"""Add tests with literal reads of a changed CSS custom-property producer.

Both immutable snapshots contribute alias edges. Changing a declaration's
selector or enclosing condition changes its producer even when its value stays
the same. CSS uses tinycss2, HTML uses turbohtml, and JavaScript uses Leaf's
existing syntax reader. The canonical test context supplies bounded helper,
constant and probe source without fixture closure. These positive witnesses
never establish independence for a test without a witness.
"""

import ast
import time
from collections import defaultdict, deque

import tinycss2
import turbohtml
from leaf.revision_artifact import ArtifactError, javascript_tree
from leaf.styles import css_block

from leaf_dev.test_select.evidence import test_function_name
from leaf_dev.test_select.timing import cpu_time


def tokens(items):
    for item in items:
        yield item
        nested = getattr(
            item, "arguments", getattr(item, "content", getattr(item, "value", []))
        )
        if isinstance(nested, list):
            yield from tokens(nested)


def variables(items):
    result = set()
    for item in tokens(items):
        if item.type == "function" and item.lower_name == "var":
            first = next(
                (x for x in item.arguments if x.type not in {"comment", "whitespace"}),
                None,
            )
            if first and first.type == "ident" and first.value.startswith("--"):
                result.add(first.value)
    return result


def meaning(items):
    return tuple(
        (item.type, item.name, meaning(item.arguments))
        if item.type == "function"
        else (item.type, meaning(item.content))
        if hasattr(item, "content")
        else (item.type, getattr(item, "value", None), getattr(item, "unit", None))
        for item in items
        if item.type not in {"comment", "whitespace"}
    )


def walk(node):
    yield node
    for child in node.named_children:
        yield from walk(child)


def literal(data, node):
    if node.type in {"string", "template_string"} and all(
        child.type == "string_fragment" for child in node.named_children
    ):
        return data[node.start_byte + 1 : node.end_byte - 1].decode()
    return None


def html_styles(source):
    tree = turbohtml.parse(source, source_locations=True)
    for element in tree.find_all("style"):
        location = element.source_location
        if location:
            yield element.text, location.start_tag.end_line - 1, False
    for element in tree.find_all(attrs={"style": True}):
        yield (
            element.attrs["style"],
            element.source_location.attrs["style"].start_line - 1,
            True,
        )


def styles(source, path, issues):
    if path.endswith(".css"):
        yield source, 0, False
    elif path.endswith(".html"):
        yield from html_styles(source)
    elif path.endswith((".js", ".mjs")) and "--" in source:
        data = source.encode()
        try:
            tree = javascript_tree(data, path)
        except ArtifactError as error:
            issues.append(str(error))
            return
        for node in walk(tree.root_node):
            text = literal(data, node)
            if text is None or "--" not in text or "{" not in text:
                continue
            if text.lstrip().startswith("<"):
                for sheet, offset, inline in html_styles(text):
                    yield sheet, node.start_point[0] + offset, inline
            else:
                yield text, node.start_point[0], False


def declarations(index, paths, issues):
    records = []

    def read(items, path, offset, selector="", conditions=()):
        for item in items:
            if item.type == "qualified-rule":
                read(
                    css_block(item.content),
                    path,
                    offset,
                    (selector + " " + tinycss2.serialize(item.prelude).strip()).strip(),
                    conditions,
                )
            elif item.type == "at-rule" and item.content is not None:
                read(
                    css_block(item.content),
                    path,
                    offset,
                    selector,
                    conditions + ((item.lower_at_keyword, meaning(item.prelude)),),
                )
            elif item.type == "declaration" and item.name.startswith("--"):
                records.append(
                    {
                        "property": item.name,
                        "selector": selector,
                        "conditions": conditions,
                        "value": meaning(item.value),
                        "important": item.important,
                        "reads": sorted(variables(item.value)),
                        "source": {
                            "path": path,
                            "start": item.source_line + offset,
                            "end": max(
                                (x.source_line for x in tokens(item.value)),
                                default=item.source_line,
                            )
                            + offset,
                            "revision": index.ref,
                        },
                    }
                )
            elif item.type == "error":
                issues.append(f"{path}:{item.source_line + offset}: {item.message}")

    for path in sorted(set(paths) & index.paths):
        if path.startswith("tests/") or not path.endswith(
            (".css", ".html", ".js", ".mjs")
        ):
            continue
        for sheet, offset, inline in styles(index.source(path), path, issues):
            read(
                css_block(sheet)
                if inline
                else tinycss2.parse_stylesheet(
                    sheet, skip_comments=True, skip_whitespace=True
                ),
                path,
                offset,
                "[inline style]" if inline else "",
            )
    return records


def changed_properties(before, after):
    groups = [defaultdict(list), defaultdict(list)]
    for group, records in zip(groups, (before, after)):
        for record in records:
            group[record["source"]["path"], record["property"]].append(record)
    result = {}

    def semantic(record):
        return tuple(
            record[name] for name in ("selector", "conditions", "value", "important")
        )

    for key in sorted(groups[0].keys() | groups[1].keys()):
        old, new = groups[0][key], groups[1][key]
        if list(map(semantic, old)) != list(map(semantic, new)):
            result.setdefault(key[1], {"property": key[1], "before": old, "after": new})
    return result


def readers(index, item, context, issues):
    issues.extend(context["omissions"])
    name = test_function_name(item)
    node = index.definition(item["file"], name, line=item.get("line"))
    parts = context["definitions"]
    if node is not None:
        parts = [index.record(item["file"], node, "test", name), *parts]
    result = {}

    def css_reads(text, source):
        if "var(" not in text:
            return
        if text.lstrip().startswith("<"):
            sheets = html_styles(text)
        elif "{" in text:
            sheets = [(text, 0, False)]
        else:
            # A CSS value can be passed directly to style.setProperty().
            sheets = [(text, 0, True)]
        for sheet, _, inline in sheets:
            items = css_block(sheet) if inline else tinycss2.parse_stylesheet(sheet)
            pending = list(items)
            while pending:
                declaration = pending.pop()
                if declaration.type == "declaration":
                    for prop in variables(declaration.value):
                        result.setdefault(prop, {**source, "kind": "css-var-reader"})
                elif (
                    declaration.type in {"qualified-rule", "at-rule"}
                    and declaration.content is not None
                ):
                    pending.extend(css_block(declaration.content))

    def js_reads(text, source, *, exact_lines=False):
        if "getPropertyValue" not in text and "var(" not in text:
            return
        data = text.encode()
        try:
            tree = javascript_tree(data, source["path"])
        except ArtifactError as error:
            issues.append(str(error))
            return
        for call in walk(tree.root_node):
            if call.type == "assignment_expression":
                target = call.child_by_field_name("left")
                if target.type == "member_expression":
                    owner = target.child_by_field_name("object")
                    if (
                        owner.type == "member_expression"
                        and data[
                            owner.child_by_field_name(
                                "property"
                            ).start_byte : owner.child_by_field_name(
                                "property"
                            ).end_byte
                        ]
                        == b"style"
                    ):
                        for fragment in walk(call.child_by_field_name("right")):
                            value = literal(data, fragment)
                            if value:
                                for prop in variables(
                                    tinycss2.parse_component_value_list(value)
                                ):
                                    result.setdefault(
                                        prop,
                                        {**source, "kind": "javascript-css-var-reader"},
                                    )
            if call.type != "call_expression":
                continue
            function = call.child_by_field_name("function")
            if function.type != "member_expression":
                continue
            prop = function.child_by_field_name("property")
            if prop is None:
                continue
            arguments = call.child_by_field_name("arguments").named_children
            if (
                data[prop.start_byte : prop.end_byte] == b"setProperty"
                and len(arguments) >= 2
            ):
                value = literal(data, arguments[1])
                if value:
                    for name in variables(tinycss2.parse_component_value_list(value)):
                        result.setdefault(
                            name, {**source, "kind": "javascript-css-var-reader"}
                        )
            if data[prop.start_byte : prop.end_byte] != b"getPropertyValue":
                continue
            value = literal(data, arguments[0]) if arguments else None
            if value and value.startswith("--"):
                witness = {**source, "kind": "javascript-property-reader"}
                if exact_lines:
                    witness.update(
                        start=source["start"] + call.start_point[0],
                        end=source["start"] + call.end_point[0],
                    )
                result.setdefault(value, witness)

    for part in parts:
        source = {key: part[key] for key in ("path", "start", "end")}
        source["revision"] = index.ref
        if part["path"].endswith(".py"):
            definition = index.module(part["path"])["definitions"].get(part["symbol"])
            if definition is None:
                continue
            for value in index.owned_walk(definition):
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    origin = {**source, "start": value.lineno, "end": value.end_lineno}
                    css_reads(value.value, origin)
                    js_reads(value.value, origin)
        else:
            js_reads(part["code"], source, exact_lines=True)
    return result


def literal_witnesses(before, after, manifest, *, contexts=None):
    """Return additive witnesses, omissions and incremental processing cost.

    Preparation can pass its already-collected canonical contexts keyed by
    nodeid; standalone callers ask the same EvidenceIndex owner for them.
    """
    wall, cpu = time.perf_counter(), cpu_time()
    issues = []
    paths = after.git("diff", "--name-only", before.ref, after.ref).splitlines()
    changes = changed_properties(
        declarations(before, paths, issues), declarations(after, paths, issues)
    )
    influence = {
        prop: {"producer": change, "aliases": []} for prop, change in changes.items()
    }
    if changes:
        edges = defaultdict(list)
        for record in declarations(before, before.paths, issues) + declarations(
            after, after.paths, issues
        ):
            for prop in record["reads"]:
                edges[prop].append(record)
        queue = deque(influence)
        while queue:
            prop = queue.popleft()
            for record in edges[prop]:
                downstream = record["property"]
                if downstream not in influence:
                    influence[downstream] = {
                        "producer": influence[prop]["producer"],
                        "aliases": [*influence[prop]["aliases"], record],
                    }
                    queue.append(downstream)
    witnesses, cache = {}, {}
    for item in manifest if changes else []:
        key = item["file"], test_function_name(item)
        if key not in cache:
            context = (
                after.test_context(item)
                if contexts is None
                else contexts[item["nodeid"]]
            )
            cache[key] = readers(after, item, context, issues)
        observed = cache[key]
        matches = [
            {
                "kind": "css-literal-reader",
                "property": prop,
                "reader": observed[prop],
                **influence[prop],
            }
            for prop in sorted(observed.keys() & influence.keys())
        ]
        if matches:
            witnesses[item["nodeid"]] = matches
    return {
        "witnesses": witnesses,
        "omissions": sorted(set(issues)),
        "cost": {
            "wall_seconds": time.perf_counter() - wall,
            "cpu_seconds": cpu_time() - cpu,
        },
    }
