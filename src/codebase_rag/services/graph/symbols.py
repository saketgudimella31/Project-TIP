"""Conservative static symbols and resolved calls; unresolved calls stay explicit."""

import ast
from pathlib import PurePosixPath

from tree_sitter import Language, Parser
import tree_sitter_javascript
import tree_sitter_typescript


def extract_symbols(sources: dict[str, str], imports: list[tuple[str, str, int]]) -> dict:
    symbols = []
    calls = []
    warnings = []
    imported: dict[str, set[str]] = {}
    for source, target, _ in imports:
        imported.setdefault(source, set()).add(target)
    python_trees = {}
    javascript_trees = {}
    aliases: dict[str, dict[str, tuple[str, str]]] = {}
    bindings: dict[str, dict[str, set[str]]] = {}

    def add(path, name, kind, line, end):
        symbol = {
            "id": f"{path}::{name}", "path": path, "name": name,
            "kind": kind, "line": line, "end_line": end,
        }
        # Overloads/redefinitions have one stable identity, with the last definition winning.
        symbols[:] = [item for item in symbols if item["id"] != symbol["id"]]
        symbols.append(symbol)

    def python_defs(node, path, scope=""):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                name = f"{scope}.{child.name}" if scope else child.name
                add(path, name, "class" if isinstance(child, ast.ClassDef) else "function",
                    child.lineno, child.end_lineno)
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    arguments = [
                        *child.args.posonlyargs, *child.args.args, *child.args.kwonlyargs,
                    ]
                    bindings[path].setdefault(name, set()).update(argument.arg for argument in arguments)
                    for argument in (child.args.vararg, child.args.kwarg):
                        if argument:
                            bindings[path][name].add(argument.arg)
                python_defs(child, path, name)
            else:
                if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
                    bindings[path].setdefault(scope, set()).add(child.id)
                python_defs(child, path, scope)

    def text(node, data):
        return data[node.start_byte:node.end_byte].decode("utf-8")

    def javascript_defs(node, path, data, scope=""):
        kinds = {
            "function_declaration": "function", "generator_function_declaration": "function",
            "method_definition": "method", "class_declaration": "class",
            "abstract_class_declaration": "class",
        }
        name_node = node.child_by_field_name("name")
        kind = kinds.get(node.type)
        if node.type == "variable_declarator":
            value = node.child_by_field_name("value")
            if name_node and name_node.type == "identifier":
                bindings[path].setdefault(scope, set()).add(text(name_node, data))
            if value and value.type in {"arrow_function", "function_expression", "function"}:
                kind = "function"
        if kind and name_node:
            short = text(name_node, data)
            name = f"{scope}.{short}" if scope else short
            add(path, name, kind, node.start_point.row + 1, node.end_point.row + 1)
            scope = name
            parameters = node.child_by_field_name("parameters")
            if node.type == "variable_declarator":
                value = node.child_by_field_name("value")
                parameters = value.child_by_field_name("parameters") if value else None
            if parameters:
                pending = list(parameters.named_children)
                while pending:
                    parameter = pending.pop()
                    if parameter.type == "identifier":
                        bindings[path].setdefault(scope, set()).add(text(parameter, data))
                    else:
                        pending.extend(parameter.named_children)
        if node.type == "import_statement":
            source_node = node.child_by_field_name("source")
            if source_node:
                spec = text(source_node, data)[1:-1]
                matches = [
                    target for target in imported.get(path, set())
                    if PurePosixPath(target).stem == PurePosixPath(spec).stem
                    or (PurePosixPath(target).stem == "index"
                        and PurePosixPath(target).parent.name == PurePosixPath(spec).name)
                ]
                if len(matches) == 1:
                    target = matches[0]
                    clause = next((c for c in node.named_children if c.type == "import_clause"), None)
                    if clause:
                        for item in clause.named_children:
                            if item.type == "identifier":
                                aliases[path][text(item, data)] = (target, "default")
                            elif item.type == "namespace_import":
                                identifier = next((c for c in item.named_children if c.type == "identifier"), None)
                                if identifier:
                                    aliases[path][text(identifier, data)] = (target, "")
                            elif item.type == "named_imports":
                                for specifier in item.named_children:
                                    original = specifier.child_by_field_name("name")
                                    alias = specifier.child_by_field_name("alias") or original
                                    if original and alias:
                                        aliases[path][text(alias, data)] = (target, text(original, data))
        for child in node.named_children:
            javascript_defs(child, path, data, scope)

    for path, content in sorted(sources.items()):
        aliases[path] = {}
        bindings[path] = {}
        if path.endswith(".py"):
            try:
                tree = ast.parse(content, filename=path)
            except SyntaxError:
                continue  # The import parser reports this error with its location.
            python_trees[path] = tree
            python_defs(tree, path)
            for node in tree.body:
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        matches = [
                            target for target in imported.get(path, set())
                            if target.removesuffix(".py").removesuffix("/__init__").replace("/", ".")
                            in {alias.name, f"src.{alias.name}"}
                        ]
                        if len(matches) == 1:
                            aliases[path][alias.asname or alias.name] = (matches[0], "")
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        candidates = []
                        for target in imported.get(path, set()):
                            module = target.removesuffix(".py").removesuffix("/__init__").replace("/", ".")
                            if module.endswith("." + alias.name) or module == alias.name:
                                candidates.append((target, ""))
                            elif node.module and (module == node.module or module.endswith("." + node.module)):
                                candidates.append((target, alias.name))
                        if len(candidates) == 1:
                            aliases[path][alias.asname or alias.name] = candidates[0]
        elif PurePosixPath(path).suffix in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}:
            language = (
                tree_sitter_typescript.language_tsx() if path.endswith(".tsx")
                else tree_sitter_typescript.language_typescript() if path.endswith(".ts")
                else tree_sitter_javascript.language()
            )
            data = content.encode()
            tree = Parser(Language(language)).parse(data)
            if tree.root_node.has_error:
                warnings.append(f"JavaScript/TypeScript parse errors in {path}; calls may be incomplete")
            javascript_trees[path] = (tree, data)
            javascript_defs(tree.root_node, path, data)

    by_id = {symbol["id"]: symbol for symbol in symbols}
    unresolved = []

    def record(path, scope, name, line):
        if not name:
            return
        parts = name.split(".")
        candidate = None
        if parts[0] in {"self", "cls", "this"} and scope:
            owner = scope.rpartition(".")[0]
            candidate = f"{path}::{owner}.{'.'.join(parts[1:])}"
        else:
            search_scope = scope
            while True:
                qualified = f"{search_scope}.{name}" if search_scope else name
                possible = f"{path}::{qualified}"
                if possible in by_id:
                    candidate = possible
                    break
                if parts[0] in bindings.get(path, {}).get(search_scope, set()):
                    break
                if not search_scope:
                    break
                search_scope = search_scope.rpartition(".")[0]
        shadowed = any(
            parts[0] in names and (not owner or scope == owner or scope.startswith(owner + "."))
            for owner, names in bindings.get(path, {}).items()
        )
        for alias, (target_path, target_name) in aliases.get(path, {}).items():
            if candidate is None and not shadowed and (name == alias or name.startswith(alias + ".")):
                suffix = name[len(alias):].lstrip(".")
                resolved = ".".join(part for part in (target_name, suffix) if part)
                possible = f"{target_path}::{resolved}"
                if possible in by_id:
                    candidate = possible
        caller_id = f"{path}::{scope}" if scope else None
        if candidate in by_id:
            calls.append({
                "source": path, "target": by_id[candidate]["path"], "line": line,
                "caller": caller_id, "callee": candidate, "name": name,
            })
        else:
            unresolved.append({"path": path, "line": line, "name": name})

    def python_calls(node, path, scope=""):
        for child in ast.iter_child_nodes(node):
            nested = scope
            if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                nested = f"{scope}.{child.name}" if scope else child.name
            if isinstance(child, ast.Call):
                record(path, scope, ast.unparse(child.func), child.lineno)
            python_calls(child, path, nested)

    def javascript_calls(node, path, data, scope=""):
        for child in node.named_children:
            nested = scope
            name_node = child.child_by_field_name("name")
            if name_node and child.type in {
                "function_declaration", "generator_function_declaration", "method_definition",
                "class_declaration", "abstract_class_declaration", "variable_declarator",
            }:
                candidate_name = f"{scope}.{text(name_node, data)}" if scope else text(name_node, data)
                if f"{path}::{candidate_name}" in by_id:
                    nested = candidate_name
            if child.type in {"call_expression", "new_expression"}:
                target = child.child_by_field_name("function") or child.child_by_field_name("constructor")
                if target:
                    record(path, scope, text(target, data), child.start_point.row + 1)
            javascript_calls(child, path, data, nested)

    for path, tree in python_trees.items():
        python_calls(tree, path)
    for path, (tree, data) in javascript_trees.items():
        javascript_calls(tree.root_node, path, data)
    return {"symbols": symbols, "calls": calls, "unresolved_calls": unresolved, "warnings": warnings}
