"""Source-backed test evidence for selection across Python/JavaScript boundaries.

A Git snapshot is parsed, never imported or executed. Python test definitions,
fixture setup and helper source are retained with exact paths/ranges/fingerprints.
The bounded closure reports its omissions explicitly. Exact imported references
are observations, not a complete dependency graph or inferred coverage labels.
Lexical owners separate definition bodies from containing declarations. Parent
fingerprints retain potentially evaluated child decorators/defaults/annotations
and class bases/keywords, while a child owns its binding/signature/body. Full
quotes are unchanged. Reflection, rebinding, inheritance and annotation evaluation
under future imports remain incomplete source context, never exclusion proofs.
Lookup ownership comes from Python's compiler symbol tables, with explicit
comprehension expression scopes when the compiler inlines them. Unsupported or
ambiguous compiler scopes remain unresolved rather than borrowing module names.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import os
import subprocess
import symtable
from collections import deque
from functools import cached_property
from pathlib import Path
from typing import Any

from leaf_dev.test_select.javascript import javascript_records


def test_function_name(item: dict) -> str:
    """Collected identity wins; parameter labels may themselves contain `::`."""
    if item.get("qualname"):
        return item["qualname"].replace(".<locals>", "")
    parts = item.get("nodeid", "").split("[", 1)[0].split("::")[1:]
    if item.get("function"):
        return ".".join([*parts[:-1], item["function"]])
    return ".".join(parts)


DEFINITIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


class EvidenceIndex:
    def __init__(
        self,
        root: str | Path,
        ref: str = "HEAD",
        *,
        helper_depth: int = 2,
        helper_chars: int = 18000,
    ):
        self.root = Path(root).resolve()
        self.ref = ref
        self.helper_depth = helper_depth
        self.helper_chars = helper_chars
        self.paths = set(self.git("ls-tree", "-r", "--name-only", ref).splitlines())
        self.sources: dict[str, str] = {}
        self.source_lines: dict[str, list[str]] = {}
        self.record_spans: dict[tuple[str, int, int], tuple[str, str]] = {}
        self.modules: dict[str, dict] = {}
        self.probe_omissions: dict[str, list[str]] = {}
        self.module_paths: dict[str, str] = {}
        self.resource_paths: dict[str, list[str]] = {}
        for path in sorted(self.paths):
            if path.endswith((".html", ".js", ".css", ".json")):
                parts = path.split("/")
                for position in range(max(1, len(parts) - 1)):
                    suffix = "/".join(parts[position:])
                    self.resource_paths.setdefault(suffix, []).append(path)
        for path in sorted(self.paths):
            if not path.endswith(".py"):
                continue
            stem = path[:-3].replace("/", ".")
            aliases = [stem]
            if path.startswith("tests/"):
                aliases += [Path(path).stem]
            for prefix in ("skills/leaf/scripts/", "dev/", "worker/"):
                if path.startswith(prefix):
                    aliases += [path[len(prefix) : -3].replace("/", ".")]
            for alias in aliases:
                alias = alias.removesuffix(".__init__")
                self.module_paths[alias] = path

    def git(self, *args: str) -> str:
        return subprocess.check_output(["git", "-C", str(self.root), *args], text=True)

    def source(self, path: str) -> str:
        if path not in self.sources:
            self.sources[path] = self.git("show", f"{self.ref}:{path}")
        return self.sources[path]

    def module(self, path: str) -> dict:
        if path in self.modules:
            return self.modules[path]
        tree = ast.parse(self.source(path), filename=path)
        candidates: dict[str, list[ast.AST]] = {}
        node_symbols: dict[ast.AST, str] = {}
        lexical_parents: dict[ast.AST, ast.AST | None] = {}
        node_scopes: dict[ast.AST, ast.AST | None] = {}
        compiler_scopes = {tree: symtable.symtable(self.source(path), path, "exec")}
        expression_locals: dict[ast.AST, set[str]] = {}
        scope_omissions = []

        def compiler_scope(node, parent, name):
            table = compiler_scopes.get(parent if parent is not None else tree)
            enclosing = parent
            while table is None and isinstance(enclosing, COMPREHENSIONS):
                enclosing = lexical_parents[enclosing]
                table = compiler_scopes.get(
                    enclosing if enclosing is not None else tree
                )
            matches = (
                [
                    child
                    for child in table.get_children()
                    if child.get_name() == name and child.get_lineno() == node.lineno
                ]
                if table is not None
                else []
            )
            compiler_scopes[node] = matches[0] if len(matches) == 1 else None
            if len(matches) != 1 and not isinstance(node, COMPREHENSIONS):
                scope_omissions.append(
                    f"compiler scope unresolved: {path}:{node.lineno}:{name}"
                )

        def visit(node, prefix="", parent=None):
            node_scopes[node] = parent if parent is not None else tree
            if isinstance(node, DEFINITIONS):
                name = f"{prefix}.{node.name}" if prefix else node.name
                candidates.setdefault(name, []).append(node)
                node_symbols[node] = name
                lexical_parents[node] = parent
                compiler_scope(node, parent, node.name)
                for field, value in ast.iter_fields(node):
                    if field == "body":
                        continue
                    for child in value if isinstance(value, list) else [value]:
                        if isinstance(child, ast.AST):
                            visit(child, prefix, parent)
                for child in node.body:
                    visit(child, name, node)
                return
            if isinstance(node, (ast.Lambda, *COMPREHENSIONS)):
                compiler_name = {
                    ast.ListComp: "listcomp",
                    ast.SetComp: "setcomp",
                    ast.DictComp: "dictcomp",
                    ast.GeneratorExp: "genexpr",
                    ast.Lambda: "lambda",
                }[type(node)]
                name = f"{prefix + '.' if prefix else ''}<{compiler_name}>@{node.lineno}:{node.col_offset}"
                node_symbols[node] = name
                lexical_parents[node] = parent
                compiler_scope(node, parent, compiler_name)
                if isinstance(node, ast.Lambda):
                    visit(node.args, prefix, parent)
                    visit(node.body, name, node)
                else:
                    # Python's compiler inlines comprehensions on some versions.
                    # Their targets still have a separate language-defined scope;
                    # the first iterable alone evaluates in the enclosing scope.
                    expression_locals[node] = {
                        child.id
                        for generator in node.generators
                        for child in ast.walk(generator.target)
                        if isinstance(child, ast.Name)
                    }
                    for position, generator in enumerate(node.generators):
                        visit(
                            generator.iter,
                            prefix if position == 0 else name,
                            parent if position == 0 else node,
                        )
                        visit(generator.target, name, node)
                        for condition in generator.ifs:
                            visit(condition, name, node)
                    for field in ("elt", "key", "value"):
                        value = getattr(node, field, None)
                        if value is not None:
                            visit(value, name, node)
                return
            if isinstance(node, (ast.Assign, ast.AnnAssign)) and (
                parent is None or isinstance(parent, ast.ClassDef)
            ):
                targets = (
                    node.targets if isinstance(node, ast.Assign) else [node.target]
                )
                for target in targets:
                    for binding in ast.walk(target):
                        if isinstance(binding, ast.Name) and isinstance(
                            binding.ctx, ast.Store
                        ):
                            name = f"{prefix}.{binding.id}" if prefix else binding.id
                            candidates.setdefault(name, []).append(node)
                            node_symbols.setdefault(node, name)
                            lexical_parents[node] = parent
            for child in ast.iter_child_nodes(node):
                visit(child, prefix, parent)

        for node in tree.body:
            visit(node)
        definitions = {
            name: nodes[0] for name, nodes in candidates.items() if len(nodes) == 1
        }
        import_declarations = self.import_declarations(
            path, (node for node in ast.walk(tree) if node_scopes.get(node) is tree)
        )
        imports = {
            name: declarations[-1][0]
            for name, declarations in import_declarations.items()
        }
        data = {
            "tree": tree,
            "definitions": definitions,
            "definition_candidates": candidates,
            "node_symbols": node_symbols,
            "lexical_parents": lexical_parents,
            "node_scopes": node_scopes,
            "compiler_scopes": compiler_scopes,
            "expression_locals": expression_locals,
            "scope_bindings": {},
            "imports": imports,
            "import_declarations": import_declarations,
            "omissions": scope_omissions
            + [
                f"ambiguous lexical binding: {path}:{name}"
                for name, nodes in candidates.items()
                if len(nodes) > 1
            ],
        }
        self.modules[path] = data
        return data

    @staticmethod
    def owned_walk(node: ast.AST):
        """Walk this owner's body and child declarations, not child bodies.

        A child function's decorators, defaults and annotations, and a child
        class's bases/keywords/decorators remain in the containing declaration.
        This is lexical source ownership, not an execution or independence proof.
        """
        queue = deque([node])
        while queue:
            current = queue.popleft()
            yield current
            for field, value in ast.iter_fields(current):
                if (
                    current is not node
                    and isinstance(current, DEFINITIONS)
                    and field == "body"
                ):
                    continue
                if isinstance(value, ast.AST):
                    queue.append(value)
                elif isinstance(value, list):
                    queue.extend(child for child in value if isinstance(child, ast.AST))

    @staticmethod
    def owned_signature(node: ast.AST) -> str:
        """Own structure plus potentially evaluated child-header expressions.

        Pure child binding/signature/body changes do not mark the containing
        owner. Decorators, defaults and annotations can affect declaration work;
        annotations are kept conservatively even with postponed evaluation.
        Class child direct execution is a separate positive dependency edge.
        """
        masked = copy.deepcopy(node)

        class Headers(ast.NodeTransformer):
            def visit(self, current):
                if current is not masked and isinstance(current, DEFINITIONS):
                    expressions = EvidenceIndex.header_expressions(current)
                    return (
                        ast.Expr(value=ast.Tuple(elts=expressions, ctx=ast.Load()))
                        if expressions
                        else None
                    )
                return super().visit(current)

        masked = Headers().visit(masked)
        return ast.dump(masked, include_attributes=False)

    @staticmethod
    def header_expressions(node: ast.AST) -> list[ast.AST]:
        """Potential declaration evaluations, excluding child binding metadata."""
        expressions = list(getattr(node, "decorator_list", []))
        if isinstance(node, ast.ClassDef):
            expressions.extend(node.bases)
            expressions.extend(keyword.value for keyword in node.keywords)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            arguments = node.args
            expressions.extend(arguments.defaults)
            expressions.extend(
                value for value in arguments.kw_defaults if value is not None
            )
            for argument in [
                *arguments.posonlyargs,
                *arguments.args,
                *arguments.kwonlyargs,
                arguments.vararg,
                arguments.kwarg,
            ]:
                if argument is not None and argument.annotation is not None:
                    expressions.append(argument.annotation)
            if node.returns is not None:
                expressions.append(node.returns)
        for parameter in getattr(node, "type_params", []):
            for field in ("bound", "default_value"):
                value = getattr(parameter, field, None)
                if value is not None:
                    expressions.append(value)
        return expressions

    def scope_for(self, path: str, node: ast.AST) -> ast.AST | None:
        """Containing lookup scope: headers use the parent, bodies their owner."""
        return self.module(path)["node_scopes"].get(node)

    def definition(self, path: str, symbol: str, *, line: int | None = None):
        """Resolve one lexical source definition; repeated bindings need a line.

        Qualified identities survive source movement between revisions. A short
        collected name may use its actual source line to disambiguate class or
        nested definitions, but never selects the first same-named definition.
        """
        module = self.module(path)
        symbol = symbol.replace(".<locals>", "")
        candidates = module["definition_candidates"].get(symbol, [])
        if len(candidates) == 1:
            return candidates[0]
        if line is None:
            return None
        if not candidates:
            candidates = [
                node
                for name, nodes in module["definition_candidates"].items()
                if name.rsplit(".", 1)[-1] == symbol.rsplit(".", 1)[-1]
                for node in nodes
                if isinstance(node, DEFINITIONS)
            ]
        matches = [
            node
            for node in candidates
            if min(
                [node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])]
            )
            <= line
            <= node.end_lineno
        ]
        return matches[0] if len(matches) == 1 else None

    def changed_definition_symbols(self, after: EvidenceIndex, path: str) -> set[str]:
        """Compare lexical owners once; full quotes stay separate source context."""
        before_definitions = (
            self.module(path)["definitions"] if path in self.paths else {}
        )
        after_definitions = (
            after.module(path)["definitions"] if path in after.paths else {}
        )
        return {
            symbol
            for symbol in before_definitions.keys() | after_definitions.keys()
            if symbol not in before_definitions
            or symbol not in after_definitions
            or self.owned_signature(before_definitions[symbol])
            != after.owned_signature(after_definitions[symbol])
        }

    def changed_import_bindings(self, after: EvidenceIndex, path: str) -> set[str]:
        """Compare each imported binding, independently of its statement span.

        Ordered declaration targets retain repeated aliases. Added, removed or
        rebound aliases change; statement formatting and unchanged neighboring
        aliases do not. This is source binding context, not proof of import side
        effects, conditional execution or dynamic module attribute behavior.
        """
        before_imports = (
            self.module(path)["import_declarations"] if path in self.paths else {}
        )
        after_imports = (
            after.module(path)["import_declarations"] if path in after.paths else {}
        )
        return {
            name
            for name in before_imports.keys() | after_imports.keys()
            if [target for target, _ in before_imports.get(name, [])]
            != [target for target, _ in after_imports.get(name, [])]
        }

    def import_declarations(self, path: str, nodes) -> dict:
        """Canonical alias targets and full statements in lexical source order."""
        declarations = {}
        for node in sorted(
            (node for node in nodes if isinstance(node, (ast.Import, ast.ImportFrom))),
            key=lambda node: (node.lineno, node.col_offset),
        ):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    declarations.setdefault(
                        alias.asname or alias.name.split(".")[0], []
                    ).append(((alias.name, None), node))
            elif isinstance(node, ast.ImportFrom):
                parts = path.split("/")[: -node.level] if node.level else []
                if node.module:
                    parts.extend(node.module.split("."))
                owner = ".".join(parts)
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    candidate = f"{owner}.{alias.name}" if owner else alias.name
                    declarations.setdefault(alias.asname or alias.name, []).append(
                        (
                            (candidate, None)
                            if candidate in self.module_paths
                            else (owner, alias.name),
                            node,
                        )
                    )
        return declarations

    def import_bindings(self, path: str, nodes) -> dict:
        """Resolve module/local imports from the canonical declaration targets."""
        return {
            name: declarations[-1][0]
            for name, declarations in self.import_declarations(path, nodes).items()
        }

    def scope_bindings(self, path: str, node: ast.AST) -> dict:
        """Compiler-owned lookup facts, including exception and pattern bindings.

        Comprehension targets have a grammar-defined expression scope even when
        this Python compiler inlines them and omits their symbol-table child.
        Ambiguous or unsupported compiler scopes never fall back to module names.
        """
        module = self.module(path)
        cache = module["scope_bindings"]
        if node not in cache:
            table = module["compiler_scopes"].get(node)
            cache[node] = {
                "symbols": {symbol.get_name(): symbol for symbol in table.get_symbols()}
                if table is not None
                else None,
                "imports": self.import_bindings(
                    path,
                    (
                        child
                        for child in ast.walk(node)
                        if module["node_scopes"].get(child) is node
                    ),
                ),
            }
        return cache[node]

    def binding(
        self, path: str, name: str, *, scope: ast.AST | str | None = None
    ) -> dict | None:
        """Name-binding owner and source target are separate canonical facts.

        External imports have a known lexical owner even without repository code.
        Parameters, local stores and local imports belong to their lexical owner;
        function free names skip implicit class namespaces. Dynamic rebinding is
        not evaluated, and a source target is retrieval rather than runtime proof.
        """
        module = self.module(path)
        if isinstance(scope, str):
            scope = self.definition(path, scope)

        def imported(qualified, spec):
            target = self.module_paths.get(spec[0])
            return {
                "owner": (path, qualified),
                "kind": "import",
                "target": (target, spec[1]) if target else None,
            }

        def declared(qualified):
            if qualified not in module["definition_candidates"]:
                return None
            unique = qualified in module["definitions"]
            return {
                "owner": (path, qualified),
                "kind": "definition" if unique else "ambiguous",
                "target": (path, qualified) if unique else None,
            }

        current = scope
        seeking_closure = False
        while current is not None and current is not module["tree"]:
            symbol = module["node_symbols"].get(current)
            if isinstance(current, ast.ClassDef) and current is not scope:
                current = module["lexical_parents"].get(current)
                continue
            if symbol is None:
                return None
            qualified = symbol + "." + name
            if isinstance(current, COMPREHENSIONS):
                if name in module["expression_locals"][current]:
                    return {"owner": (path, qualified), "kind": "local", "target": None}
                current = module["lexical_parents"].get(current)
                continue
            facts = self.scope_bindings(path, current)
            if facts["symbols"] is None:
                return None
            binding = facts["symbols"].get(name)
            if binding is None:
                return None
            if binding.is_global():
                seeking_closure = False
                break
            if binding.is_free() or binding.is_nonlocal():
                seeking_closure = True
                current = module["lexical_parents"].get(current)
                continue
            if binding.is_imported():
                spec = facts["imports"].get(name)
                return imported(qualified, spec) if spec is not None else None
            if binding.is_local():
                definition = declared(qualified)
                if definition is not None:
                    return definition
                return {
                    "owner": (path, qualified),
                    "kind": "parameter" if binding.is_parameter() else "local",
                    "target": None,
                }
            return None
        if seeking_closure:
            return None
        if name in module["imports"]:
            return imported(name, module["imports"][name])
        return declared(name)

    def binding_owner(
        self, path: str, name: str, *, scope: ast.AST | str | None = None
    ) -> tuple[str, str] | None:
        """Project the canonical name owner, including unresolved external imports."""
        binding = self.binding(path, name, scope=scope)
        return binding["owner"] if binding is not None else None

    def resolve(
        self, path: str, name: str, *, scope: ast.AST | str | None = None
    ) -> tuple[str, str | None] | None:
        """Retrieve lexical or qualified source bindings, without runtime dispatch.

        Function free names skip class namespaces. Explicit class attributes
        and unshadowed self/cls in a direct method may name declared members;
        inheritance, reflection, descriptors and instance-value flow remain
        unresolved. A resolved source spelling is not proof that a call executes.
        """
        module = self.module(path)
        if isinstance(scope, str):
            scope = self.definition(path, scope)
        name = name.replace(".<locals>", "")
        head, separator, tail = name.partition(".")
        if separator:
            parent = module["lexical_parents"].get(scope)
            arguments = getattr(scope, "args", None)
            positional = [*arguments.posonlyargs, *arguments.args] if arguments else []
            decorators = [
                d.func if isinstance(d, ast.Call) else d
                for d in getattr(scope, "decorator_list", [])
            ]
            static = any(
                isinstance(d, ast.Name) and d.id == "staticmethod" for d in decorators
            )
            if head in {"self", "cls"}:
                if not (
                    isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and isinstance(parent, ast.ClassDef)
                    and positional
                    and positional[0].arg == head
                    and not static
                ):
                    return None
                symbols = self.scope_bindings(path, scope)["symbols"]
                if symbols is None or symbols[head].is_assigned():
                    return None
                qualified = module["node_symbols"][parent] + "." + tail
                return (path, qualified) if qualified in module["definitions"] else None
            owner = self.resolve(path, head, scope=scope)
            if owner is None:
                return None
            target, symbol = owner
            qualified = f"{symbol}.{tail}" if symbol else tail
            target_module = self.module(target)
            if qualified in target_module["definitions"]:
                return target, qualified
            # A named imported facade can be followed by definition_origin;
            # a known function's arbitrary attribute is not that function body.
            if symbol and symbol in target_module["imports"]:
                return target, qualified
            return None
        binding = self.binding(path, name, scope=scope)
        return binding["target"] if binding is not None else None

    def record(self, path: str, node: ast.AST, kind: str, symbol: str = "") -> dict:
        start = min(
            [node.lineno] + [x.lineno for x in getattr(node, "decorator_list", [])]
        )
        key = (path, start, node.end_lineno)
        if key not in self.record_spans:
            if path not in self.source_lines:
                self.source_lines[path] = self.source(path).splitlines()
            code = "\n".join(self.source_lines[path][start - 1 : node.end_lineno])
            self.record_spans[key] = code, hashlib.sha256(code.encode()).hexdigest()
        code, fingerprint = self.record_spans[key]
        return {
            "path": path,
            "start": start,
            "end": node.end_lineno,
            "symbol": symbol,
            "kind": kind,
            "sha256": fingerprint,
            "code": code,
        }

    def definition_origin(
        self, path: str, symbol: str
    ) -> tuple[str, str, ast.AST] | None:
        """Follow named re-exports to code while retaining binding identities elsewhere.

        Consumers depend on the facade binding as well as its current definition.
        Graph edges preserve both; source extraction needs the actual definition.
        Cyclic or external imports have no statically available definition.
        """
        seen = set()
        while (path, symbol) not in seen:
            seen.add((path, symbol))
            module = self.module(path)
            if symbol in module["definitions"]:
                return path, symbol, module["definitions"][symbol]
            target = self.resolve(path, symbol)
            if target is None or target[1] is None:
                return None
            path, symbol = target
        return None

    @cached_property
    def fixtures(self) -> dict[str, list[tuple[str, ast.AST]]]:
        result: dict[str, list] = {}
        for path in sorted(self.paths):
            if not path.startswith("tests/") or not path.endswith(".py"):
                continue
            for node in self.module(path)["definitions"].values():
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for decorator in node.decorator_list:
                    func = (
                        decorator.func if isinstance(decorator, ast.Call) else decorator
                    )
                    if isinstance(func, ast.Attribute) and func.attr == "fixture":
                        fixture_name = node.name
                        if isinstance(decorator, ast.Call):
                            for kw in decorator.keywords:
                                if kw.arg == "name" and isinstance(
                                    kw.value, ast.Constant
                                ):
                                    fixture_name = kw.value.value
                        result.setdefault(fixture_name, []).append((path, node))
        return result

    @cached_property
    def javascript(self) -> dict:
        # Parse only probe modules: shared browser startup otherwise dominates packets.
        paths = sorted(
            p for p in self.paths if "/render-checks/" in p and p.endswith(".js")
        )
        return {p: javascript_records(self.source(p), p) for p in paths}

    def probe(self, name: str) -> list[dict]:
        output = []
        omissions = []
        self.probe_omissions[name] = omissions
        seen = set()
        queue = deque(
            (path, name, 0)
            for path, data in self.javascript.items()
            if name in data["definitions"]
        )
        chars = 0
        while queue:
            path, symbol, depth = queue.popleft()
            if (path, symbol) in seen:
                continue
            seen.add((path, symbol))
            definition = self.javascript[path]["definitions"][symbol]
            omissions.extend(
                f"probe import unresolved: {path}:{item['line']}: {item['reason']}"
                for item in self.javascript[path]["unresolved_imports"]
            )
            if depth and chars + len(definition["code"]) > 12000:
                omissions.append(f"probe helper code bounded: {path}:{symbol}")
                continue
            chars += len(definition["code"])
            output.append(
                {
                    "path": path,
                    "symbol": symbol,
                    "kind": "probe" if depth == 0 else "probe-helper",
                    "sha256": hashlib.sha256(definition["code"].encode()).hexdigest(),
                    **definition,
                }
            )
            if depth == 1 and any(
                r in self.javascript[path]["definitions"] for r in definition["refs"]
            ):
                omissions.append(
                    f"probe helper closure bounded at one hop: {path}:{symbol}"
                )
            if depth < 1:
                for reference in definition["refs"]:
                    if reference in self.javascript[path]["definitions"]:
                        queue.append((path, reference, depth + 1))
                    for imported in self.javascript[path]["imports"]:
                        target = (Path(path).parent / imported["source"]).as_posix()
                        target = os.path.normpath(target)
                        for binding in imported["names"]:
                            if (
                                binding["local"] == reference
                                and target in self.javascript
                                and binding["remote"]
                                in self.javascript[target]["definitions"]
                            ):
                                queue.append((target, binding["remote"], depth + 1))
        return output

    def test_context(self, item: dict[str, Any]) -> dict:
        """Code explicitly reached from this test, without shared fixture expansion.

        Direct helpers, constants and named browser probes expose what a Python
        assertion actually observes. Source closure is bounded; absence from
        this packet is never evidence that a dependency is independent.
        """
        reading = self.extract({**item, "fixturenames": [], "fixturedefs": []})
        records = [*reading["probes"], *reading["helpers"]]
        return {
            "definitions": [
                {k: record[k] for k in ("path", "start", "end", "symbol", "code")}
                for record in records
            ],
            "resources": [
                {k: resource[k] for k in ("path", "code", "chars")}
                for resource in reading["resources"]
            ],
            "omissions": reading["evidence_missing"],
        }

    def extract(self, item: dict[str, Any]) -> dict:
        path = item["file"]
        if path not in self.paths:
            return {
                "nodeid": item["nodeid"],
                "body": None,
                "fixtures": [],
                "helpers": [],
                "refs": [],
                "probes": [],
                "resources": [],
                "params": item.get("params", {}),
                "evidence_missing": ["test source absent at selected Git ref"],
            }
        module = self.module(path)
        name = test_function_name(item)
        node = self.definition(path, name, line=item["line"])
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return {
                "nodeid": item["nodeid"],
                "evidence_missing": ["test definition not found"],
                "body": None,
                "fixtures": [],
                "helpers": [],
                "refs": [],
                "probes": [],
                "resources": [],
                "params": item.get("params", {}),
            }
        name = module["node_symbols"][node]
        body = self.record(path, node, "test", name)
        output = {
            "nodeid": item["nodeid"],
            "body": body,
            "fixtures": [],
            "helpers": [],
            "refs": [],
            "probes": [],
            "resources": [],
            "evidence_missing": list(module["omissions"]),
            "params": item.get("params", {}),
        }
        if "fixturenames" not in item:
            output["evidence_missing"].append(
                "fixture inventory absent: static function arguments only"
            )
        if "[" in item["nodeid"] and "params" not in item:
            output["evidence_missing"].append("parameter values not collected")
        queue = deque([(path, node, 0)])
        seen = {(path, name)}
        fixtures = item.get("fixturenames", [a.arg for a in node.args.args])
        for fixture in fixtures:
            exact = [
                d
                for d in item.get("fixturedefs", [])
                if d["name"] == fixture and d["path"] in self.paths
            ]
            matches = [
                (
                    d["path"],
                    self.definition(
                        d["path"], test_function_name(d), line=d.get("line")
                    ),
                )
                for d in exact
            ]
            matches = (
                [
                    (p, n)
                    for p, n in matches
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                if exact
                else self.fixtures.get(fixture, [])
            )
            if exact and not matches:
                output["evidence_missing"].append(
                    f"collected fixture definition unresolved: {fixture}"
                )
            scoped = [
                (p, n) for p, n in matches if p == path or p.endswith("/conftest.py")
            ]
            for p, n in scoped or matches:
                symbol = self.module(p)["node_symbols"][n]
                if (p, symbol) not in seen:
                    seen.add((p, symbol))
                    output["fixtures"].append(self.record(p, n, "fixture", symbol))
                    queue.append((p, n, 1))
        chars = sum(len(x["code"]) for x in output["fixtures"])
        ref_keys = set()
        resource_keys = set()
        resource_budget = 20000
        resource_chars = 0
        probe_keys = set()
        while queue:
            owner, current, depth = queue.popleft()
            aliases = {}
            for candidate in self.owned_walk(current):
                if (
                    isinstance(candidate, ast.For)
                    and isinstance(candidate.target, ast.Name)
                    and isinstance(candidate.iter, (ast.Tuple, ast.List))
                ):
                    aliases[candidate.target.id] = [
                        x.id for x in candidate.iter.elts if isinstance(x, ast.Name)
                    ]
            for child in self.owned_walk(current):
                referenced: list[tuple[str, str | None, str]] = []
                scope = self.scope_for(owner, child)
                if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
                    resolved = self.resolve(owner, child.id, scope=scope)
                    if resolved:
                        referenced.append((*resolved, child.id))
                if isinstance(child, ast.Attribute) and isinstance(
                    child.value, ast.Name
                ):
                    for alias in aliases.get(child.value.id, [child.value.id]):
                        resolved = self.resolve(
                            owner, alias + "." + child.attr, scope=scope
                        )
                        if resolved:
                            referenced.append(
                                (
                                    resolved[0],
                                    resolved[1],
                                    ast.unparse(child),
                                )
                            )
                if isinstance(child, ast.Call):
                    func = child.func
                    called = (
                        func.attr
                        if isinstance(func, ast.Attribute)
                        else func.id
                        if isinstance(func, ast.Name)
                        else ""
                    )
                    if (
                        called in {"evaluate_probe", "wait_for_probe"}
                        and len(child.args) > 1
                        and isinstance(child.args[1], ast.Constant)
                        and isinstance(child.args[1].value, str)
                    ):
                        probe_name = child.args[1].value
                        if probe_name not in probe_keys:
                            probe_keys.add(probe_name)
                            found = self.probe(probe_name)
                            output["probes"].extend(found)
                            output["evidence_missing"].extend(
                                self.probe_omissions[probe_name]
                            )
                            if not found:
                                output["evidence_missing"].append(
                                    f"probe not resolved: {probe_name}"
                                )
                    if (
                        called in {"setattr", "delattr"}
                        and len(child.args) >= 2
                        and isinstance(child.args[0], ast.Name)
                        and isinstance(child.args[1], ast.Constant)
                    ):
                        for alias in aliases.get(child.args[0].id, [child.args[0].id]):
                            resolved = self.resolve(
                                owner,
                                alias + "." + str(child.args[1].value),
                                scope=scope,
                            )
                            if resolved:
                                referenced.append(
                                    (
                                        resolved[0],
                                        resolved[1],
                                        ast.unparse(child),
                                    )
                                )
                for target, symbol, via in referenced:
                    key = (target, symbol, owner, child.lineno)
                    if key not in ref_keys:
                        ref_keys.add(key)
                        output["refs"].append(
                            {
                                "path": target,
                                "symbol": symbol,
                                "via": via,
                                "witness": {
                                    "path": owner,
                                    "start": child.lineno,
                                    "end": child.end_lineno,
                                },
                            }
                        )
                    if (
                        symbol
                        and (target, symbol) not in seen
                        and target.startswith("tests/")
                    ):
                        origin = self.definition_origin(target, symbol)
                        if origin:
                            target, symbol, helper = origin
                            if (target, symbol) in seen:
                                continue
                            record = self.record(target, helper, "helper", symbol)
                            seen.add((target, symbol))
                            if (
                                depth < self.helper_depth
                                and chars + len(record["code"]) <= self.helper_chars
                            ):
                                chars += len(record["code"])
                                output["helpers"].append(record)
                                queue.append((target, helper, depth + 1))
                            else:
                                output["evidence_missing"].append(
                                    f"helper closure bounded: {target}:{symbol}"
                                )
                if isinstance(child, ast.Constant) and isinstance(child.value, str):
                    text = child.value
                    matches = (
                        [text]
                        if text in self.paths
                        else self.resource_paths.get(text, [])
                    )
                    for resource in sorted(matches):
                        if resource not in resource_keys:
                            resource_keys.add(resource)
                            content = self.source(resource)
                            included = (
                                len(content) <= 16000
                                and resource_chars + len(content) <= resource_budget
                            )
                            output["resources"].append(
                                {
                                    "path": resource,
                                    "sha256": hashlib.sha256(
                                        content.encode()
                                    ).hexdigest(),
                                    "chars": len(content),
                                    "witness": {
                                        "path": owner,
                                        "start": child.lineno,
                                        "end": child.end_lineno,
                                    },
                                    "code": content if included else None,
                                }
                            )
                            if included:
                                resource_chars += len(content)
                            else:
                                output["evidence_missing"].append(
                                    f"resource code bounded: {resource}"
                                )
        for value in self.param_paths(item.get("params", {})):
            if value in self.paths and value not in resource_keys:
                resource_keys.add(value)
                content = self.source(value)
                included = (
                    len(content) <= 16000
                    and resource_chars + len(content) <= resource_budget
                )
                output["resources"].append(
                    {
                        "path": value,
                        "sha256": hashlib.sha256(content.encode()).hexdigest(),
                        "chars": len(content),
                        "via": "collected parameter",
                        "code": content if included else None,
                    }
                )
                if included:
                    resource_chars += len(content)
                else:
                    output["evidence_missing"].append(f"resource code bounded: {value}")
        return output

    def param_paths(self, value):
        if isinstance(value, dict):
            if "path" in value and isinstance(value["path"], str):
                yield value["path"]
            for child in value.values():
                yield from self.param_paths(child)
        elif isinstance(value, list):
            for child in value:
                yield from self.param_paths(child)
        elif isinstance(value, str) and value in self.paths:
            yield value
