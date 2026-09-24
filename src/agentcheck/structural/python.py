"""Public symbols of a Python module (plan v2, decision 3).

Public: module-level functions and classes whose name doesn't start with `_` — or exactly the
names in a literal `__all__` — and the methods of those classes that don't start with `_`, plus
dunders (`__init__` is part of how a class is called). Only top-level definitions count: a
function defined under `if TYPE_CHECKING:` or inside another function isn't API.
"""

from __future__ import annotations

import tree_sitter as ts
import tree_sitter_python

from agentcheck.structural.model import Parsed, Symbol, collapse, first_error_line

_PARSER = ts.Parser(ts.Language(tree_sitter_python.language()))


def _is_public_name(name: str) -> bool:
    return not name.startswith("_") or (name.startswith("__") and name.endswith("__"))


def _unwrap(node: ts.Node) -> ts.Node:
    """The definition inside a `decorated_definition`, or the node itself."""
    if node.type == "decorated_definition":
        inner = node.child_by_field_name("definition")
        if inner is not None:
            return inner
    return node


def _signature(fn: ts.Node) -> str:
    params = collapse(fn.child_by_field_name("parameters").text)
    returns = fn.child_by_field_name("return_type")
    return f"{params} -> {collapse(returns.text)}" if returns is not None else params


def _literal_all(module: ts.Node) -> set[str] | None:
    """Names in `__all__ = [...]` / `(...)` when every element is a string literal; else None.

    Anything built dynamically returns None, and the caller falls back to the underscore rule —
    treating it as "exports nothing" would hide every removal.
    """
    for stmt in module.children:
        if stmt.type != "expression_statement" or not stmt.named_children:
            continue
        assign = stmt.named_children[0]
        if assign.type != "assignment":
            continue
        left, right = assign.child_by_field_name("left"), assign.child_by_field_name("right")
        if left is None or left.text != b"__all__":
            continue
        if right is None or right.type not in ("list", "tuple"):
            return None
        names = set()
        for element in right.named_children:
            if element.type != "string":
                return None
            content = [c for c in element.named_children if c.type == "string_content"]
            if len(content) != 1:
                return None
            names.add(content[0].text.decode("utf-8", errors="replace"))
        return names
    return None


def extract(source: bytes) -> Parsed:
    tree = _PARSER.parse(source)
    root = tree.root_node
    if root.has_error:
        return Parsed(ok=False, error_line=first_error_line(root))

    exported = _literal_all(root)
    public: dict[str, Symbol] = {}
    for stmt in root.children:
        node = _unwrap(stmt)
        if node.type not in ("function_definition", "class_definition"):
            continue
        name = node.child_by_field_name("name").text.decode("utf-8", errors="replace")
        if exported is not None and name not in exported:
            continue
        if exported is None and name.startswith("_"):
            continue
        line = node.start_point.row + 1
        if node.type == "function_definition":
            public[name] = Symbol(name, "function", _signature(node), line)
            continue
        public[name] = Symbol(name, "class", None, line)
        body = node.child_by_field_name("body")
        for member in body.children if body is not None else ():
            method = _unwrap(member)
            if method.type != "function_definition":
                continue
            mname = method.child_by_field_name("name").text.decode("utf-8", errors="replace")
            if _is_public_name(mname):
                qualified = f"{name}.{mname}"
                public[qualified] = Symbol(qualified, "method", _signature(method), method.start_point.row + 1)
    return Parsed(ok=True, public=public)
