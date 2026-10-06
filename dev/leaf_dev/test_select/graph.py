"""Additive source-reference closure across both immutable revisions.

A test starts at its own definition and its active collected fixtures. Ordinary
Python references and declared Click routes reached by literal CliRunner argv
add mandatory tests. Dynamic
browser/process relationships remain incomplete and are left to the model arm.
This graph never excludes a test. A fixture forces selection only when its
ordinary source-reference path reaches a changed symbol.
"""

import ast
import re
import subprocess
from collections import Counter, deque


def preload_python(index):
    paths = sorted(p for p in index.paths if p.endswith(".py"))
    payload = "".join(f"{index.ref}:{p}\n" for p in paths).encode()
    response = subprocess.check_output(
        ["git", "-C", str(index.root), "cat-file", "--batch"], input=payload
    )
    offset = 0
    for path in paths:
        end = response.index(b"\n", offset)
        header = response[offset:end].split()
        if len(header) != 3 or header[1] != b"blob":
            raise ValueError(f"Unexpected Git object for {path}")
        size = int(header[2])
        index.sources[path] = response[end + 1 : end + 1 + size].decode()
        offset = end + 2 + size
    if offset != len(response):
        raise ValueError("Unconsumed Git objects")


def changed_python(indexes, base, candidate):
    hunks = {}
    path = None
    for line in (
        indexes[-1]
        .git("diff", "--no-renames", "--unified=0", base, candidate)
        .splitlines()
    ):
        if line.startswith("diff --git a/"):
            path = line.split(" b/", 1)[1]
        elif line.startswith("@@ ") and path.endswith(".py"):
            match = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))?", line)
            a, ac, b, bc = (int(x) if x is not None else 1 for x in match.groups())
            hunks.setdefault(path, []).append(
                ((a, a + max(ac - 1, 0)), (b, b + max(bc - 1, 0)))
            )
    changed = set()
    owned_changes = {
        path: indexes[0].changed_definition_symbols(indexes[-1], path) for path in hunks
    }
    import_changes = {
        path: indexes[0].changed_import_bindings(indexes[-1], path) for path in hunks
    }
    for index in indexes:
        for path in hunks:
            if path not in index.paths:
                continue
            module = index.module(path)

            # Import bindings affect definitions that read them. Treating an import
            # as a change to every definition invents dependency edges between
            # otherwise independent functions. Collection checks importability.
            changed_bindings = import_changes[path]
            changed.update((path, name) for name in changed_bindings)
            for name, node in module["definitions"].items():
                reads_changed_binding = any(
                    isinstance(child, ast.Name)
                    and isinstance(child.ctx, ast.Load)
                    and child.id in changed_bindings
                    and index.binding_owner(
                        path, child.id, scope=index.scope_for(path, child)
                    )
                    == (path, child.id)
                    for child in index.owned_walk(node)
                )
                if name in owned_changes[path] or reads_changed_binding:
                    changed.add((path, name))
    return changed


def reference(index, path, node):
    """Resolve only named lexical/module/class paths, never arbitrary instances."""
    scope = index.scope_for(path, node)
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    return index.resolve(path, ".".join([node.id, *reversed(parts)]), scope=scope)


def constructors(index, target, seen=None):
    """Positive constructor edges for a source-resolved class call.

    A class reference alone does not execute its method bodies. Calling a class
    can reach its known __new__/__init__, including a source-resolved base when
    the derived class does not declare the corresponding method. Dynamic bases,
    metaclasses and descriptors remain unresolved, rather than exclusion proof.
    """
    if target is None or target[1] is None:
        return set()
    seen = set() if seen is None else seen
    if target in seen:
        return set()
    seen.add(target)
    origin = index.definition_origin(*target)
    if origin is None:
        return set()
    path, symbol, node = origin
    if not isinstance(node, ast.ClassDef):
        return set()
    result = set()
    inherited = set()
    for base in node.bases:
        inherited.update(constructors(index, reference(index, path, base), seen))
    for method in ("__init__", "__new__"):
        own = f"{symbol}.{method}"
        if index.definition(path, own) is not None:
            result.add((path, own))
        else:
            result.update(t for t in inherited if t[1].rsplit(".", 1)[-1] == method)
    return result


def click_routes(index):
    """Read declared Click group/command registration; never import the CLI."""
    routes = {}
    for path in sorted(p for p in index.paths if p.endswith(".py")):
        for name, node in index.module(path)["definitions"].items():
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if (
                    not isinstance(decorator, ast.Call)
                    or not isinstance(decorator.func, ast.Attribute)
                    or decorator.func.attr not in {"command", "group"}
                ):
                    continue
                parent = reference(index, path, decorator.func.value)
                if parent is None or parent[1] is None:
                    continue
                explicit = next(
                    (
                        kw.value.value
                        for kw in decorator.keywords
                        if kw.arg == "name" and isinstance(kw.value, ast.Constant)
                    ),
                    None,
                )
                default_name = node.name.lower().replace("_", "-")
                prefix, separator, suffix = default_name.rpartition("-")
                if separator and suffix in {"command", "cmd", "group", "grp"}:
                    default_name = prefix
                declared = (
                    decorator.args[0].value
                    if decorator.args
                    and isinstance(decorator.args[0], ast.Constant)
                    and isinstance(decorator.args[0].value, str)
                    else explicit or default_name
                )
                routes.setdefault(parent, {})[declared] = (path, name)
    return routes


def routed_invoke(index, path, call, routes):
    if (
        not isinstance(call.func, ast.Attribute)
        or call.func.attr != "invoke"
        or len(call.args) < 2
    ):
        return None
    root = reference(index, path, call.args[0])
    argv = call.args[1]
    if root not in routes or not isinstance(argv, (ast.List, ast.Tuple)):
        return None
    current = root
    words = []
    for arg in argv.elts:
        if current not in routes:
            return current, words
        if not isinstance(arg, ast.Constant) or not isinstance(arg.value, str):
            return None
        if arg.value not in routes[current]:
            return None
        words.append(arg.value)
        current = routes[current][arg.value]
    return (current, words) if current not in routes else None


def graph(index):
    ordinary_edges = {}
    dispatch_edges = {}
    unresolved_calls = Counter()
    routes = click_routes(index)
    bridges = []
    for path in sorted(p for p in index.paths if p.endswith(".py")):
        module = index.module(path)
        for name in module["imports"]:
            if name in module["definitions"]:
                continue
            target = index.resolve(path, name)
            if target and target[1] is not None:
                ordinary_edges[(path, name)] = {target}
                dispatch_edges[(path, name)] = {target}
        for name, node in module["definitions"].items():
            root = (path, name)
            refs = set()
            dispatch_refs = set()

            for child in index.owned_walk(node):
                if (
                    isinstance(child, ast.Name)
                    and isinstance(child.ctx, ast.Load)
                    or isinstance(child, ast.Attribute)
                ):
                    target = reference(index, path, child)
                    if target and target[1] is not None:
                        refs.add(target)
                elif isinstance(child, ast.Call):
                    target = reference(index, path, child.func)
                    refs.update(constructors(index, target))
                    if isinstance(child.func, ast.Attribute) and target is None:
                        unresolved_calls["chained-or-instance-method"] += 1
                elif isinstance(child, ast.ClassDef) and child is not node:
                    # A nested class executes its own body when its containing
                    # definition reaches this declaration, unlike a function body.
                    refs.add((path, module["node_symbols"][child]))
                if (
                    isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Name)
                    and child.func.id in {"setattr", "delattr"}
                    and len(child.args) >= 2
                    and isinstance(child.args[0], ast.Name)
                    and isinstance(child.args[1], ast.Constant)
                ):
                    target = index.resolve(
                        path,
                        f"{child.args[0].id}.{child.args[1].value}",
                        scope=index.scope_for(path, child.args[0]),
                    )
                    if target and target[1] is not None:
                        refs.add(target)
                if isinstance(child, ast.Call):
                    routed = routed_invoke(index, path, child, routes)
                    if routed:
                        target, words = routed
                        dispatch_refs.add(target)
                        bridges.append(
                            {
                                "kind": "click-literal-route",
                                "from": root,
                                "to": target,
                                "argv_prefix": words,
                                "path": path,
                                "line": child.lineno,
                                "ref": index.ref,
                            }
                        )
            ordinary_edges[root] = refs - {root}
            dispatch_edges[root] = (refs | dispatch_refs) - {root}
    return ordinary_edges, dispatch_edges, unresolved_calls, bridges


def influence_paths(edges, changed):
    reverse = {}
    for root, targets in edges.items():
        for target in targets:
            reverse.setdefault(target, set()).add(root)
    queue = deque((r, [r]) for r in sorted(changed))
    paths = {}
    while queue:
        current, path = queue.popleft()
        if current in paths:
            continue
        paths[current] = path
        queue.extend((n, [n] + path) for n in sorted(reverse.get(current, ())))
    return paths


def path_to_change(paths, roots):
    options = [paths[r] for r in roots if r in paths]
    return min(options, key=lambda p: (len(p), p)) if options else None
