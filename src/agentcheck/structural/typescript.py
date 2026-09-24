"""Public symbols of a TypeScript/JavaScript module (plan v2, decision 3).

Public: `export`ed functions (overloads included), `export`ed `const` arrow or function
expressions, `export`ed classes and their methods not marked `private` or `#`, `export default`,
and local declarations re-exported with `export { a, b as c }`.
"""

from __future__ import annotations

from dataclasses import replace

import tree_sitter as ts
import tree_sitter_typescript

from agentcheck.structural.model import Parsed, Symbol, collapse, first_error_line

_TS = ts.Parser(ts.Language(tree_sitter_typescript.language_typescript()))
# JSX only parses with the TSX grammar, and plain JS is valid TSX: `.js` goes through it too, so a
# React component in a `.js` file isn't reported as broken syntax.
_TSX = ts.Parser(ts.Language(tree_sitter_typescript.language_tsx()))

TS_EXTENSIONS = {".ts", ".mts", ".cts"}
TSX_EXTENSIONS = {".tsx", ".js", ".jsx", ".mjs", ".cjs"}

_FUNCTIONS = ("function_declaration", "generator_function_declaration", "function_signature")
_FUNCTION_VALUES = ("arrow_function", "function_expression", "function", "generator_function")


def _text(node: ts.Node | None) -> str:
    return node.text.decode("utf-8", errors="replace") if node is not None else ""


def _signature(fn: ts.Node) -> str:
    params = fn.child_by_field_name("parameters")
    if params is None:  # `x => x`: a single bare parameter
        params = fn.child_by_field_name("parameter")
    sig = collapse(params.text) if params is not None else "()"
    returns = fn.child_by_field_name("return_type")
    return f"{sig}{collapse(returns.text)}" if returns is not None else sig


def _is_private_method(method: ts.Node) -> bool:
    if _text(method.child_by_field_name("name")).startswith("#"):
        return True
    return any(c.type == "accessibility_modifier" and c.text == b"private" for c in method.children)


class _Collector:
    def __init__(self) -> None:
        self.public: dict[str, Symbol] = {}
        # Local, not-exported declarations, for `export { name }` later in the file.
        self.local: dict[str, list[Symbol]] = {}

    def add(self, symbols: list[Symbol], exported: bool) -> None:
        for sym in symbols:
            if exported:
                self._put(sym)
            else:
                self.local.setdefault(sym.name.split(".")[0], []).append(sym)

    def _put(self, sym: Symbol) -> None:
        # Overloads share a name: their signatures are joined in source order.
        existing = self.public.get(sym.name)
        if existing is not None and sym.signature is not None and existing.signature is not None:
            sym = Symbol(sym.name, sym.kind, f"{existing.signature} | {sym.signature}", existing.line)
        self.public[sym.name] = sym

    def re_export(self, local: str, alias: str) -> None:
        for sym in self.local.get(local, []):
            self._put(replace(sym, name=alias + sym.name[len(local):]))


def _declared(node: ts.Node, default_name: str | None = None) -> list[Symbol]:
    """Symbols a declaration introduces, exported or not."""
    line = node.start_point.row + 1
    name = _text(node.child_by_field_name("name")) or default_name
    if node.type in _FUNCTIONS or (node.type in _FUNCTION_VALUES and default_name):
        return [Symbol(name, "function", _signature(node), line)] if name else []
    if node.type in ("class_declaration", "class", "abstract_class_declaration"):
        if not name:
            return []
        symbols = [Symbol(name, "class", None, line)]
        body = node.child_by_field_name("body")
        for member in body.named_children if body is not None else ():
            if member.type in ("method_definition", "method_signature") and not _is_private_method(member):
                qualified = f"{name}.{_text(member.child_by_field_name('name'))}"
                symbols.append(Symbol(qualified, "method", _signature(member), member.start_point.row + 1))
        return symbols
    if node.type == "lexical_declaration":
        symbols = []
        for decl in node.named_children:
            value = decl.child_by_field_name("value")
            if decl.type == "variable_declarator" and value is not None and value.type in _FUNCTION_VALUES:
                vname = _text(decl.child_by_field_name("name"))
                symbols.append(Symbol(vname, "function", _signature(value), decl.start_point.row + 1))
        return symbols
    return []


def extract(source: bytes, tsx: bool = False) -> Parsed:
    tree = (_TSX if tsx else _TS).parse(source)
    root = tree.root_node
    if root.has_error:
        return Parsed(ok=False, error_line=first_error_line(root))

    out = _Collector()
    clauses: list[ts.Node] = []
    for stmt in root.named_children:
        if stmt.type != "export_statement":
            out.add(_declared(stmt), exported=False)
            continue
        is_default = any(c.type == "default" for c in stmt.children)
        declaration = stmt.child_by_field_name("declaration")
        value = stmt.child_by_field_name("value")
        if declaration is not None:
            symbols = _declared(declaration)
            if is_default and symbols:
                # Importers see it as `default`: renaming the declaration changes nothing for them.
                head = symbols[0].name
                symbols = [replace(s, name="default" + s.name[len(head):]) for s in symbols]
            out.add(symbols, exported=True)
        elif is_default and value is not None:
            if value.type == "identifier":
                out.re_export(_text(value), "default")
            else:
                out.add(_declared(value, default_name="default"), exported=True)
        else:
            clauses.extend(c for c in stmt.named_children if c.type == "export_clause")

    # `export { a, b as c }` may come before or after the declarations it names.
    for clause in clauses:
        for spec in clause.named_children:
            if spec.type == "export_specifier":
                local = _text(spec.child_by_field_name("name"))
                alias = _text(spec.child_by_field_name("alias")) or local
                out.re_export(local, alias)
    imports = []
    for stmt in root.named_children:
        source = stmt.child_by_field_name("source") if stmt.type in ("import_statement", "export_statement") else None
        fragment = next((c for c in source.named_children if c.type == "string_fragment"), None) if source else None
        if fragment is not None:
            imports.append(_text(fragment))
    return Parsed(ok=True, public=out.public, imports=imports)
