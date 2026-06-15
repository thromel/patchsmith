from __future__ import annotations

import ast
import builtins
from dataclasses import dataclass


@dataclass(frozen=True)
class ReplacementSpan:
    start_line: int
    end_line: int


def introduced_unbound_python_names(
    *,
    source_after_replacement: str,
    replacement_offset: int,
    replacement_length: int,
) -> tuple[str, ...]:
    if replacement_length <= 0:
        return ()
    try:
        tree = ast.parse(source_after_replacement)
    except SyntaxError:
        return ()
    span = _span_from_offset(
        source_after_replacement,
        offset=replacement_offset,
        length=replacement_length,
    )
    loaded_names = _loaded_names_in_span(tree, span)
    if not loaded_names:
        return ()
    available_names = _available_names_at_span(tree, span)
    bound_in_replacement = _bound_names_in_span(tree, span)
    missing = loaded_names - available_names - bound_in_replacement
    return tuple(sorted(missing))


def removed_imported_python_names_still_used(
    *,
    source_before_replacement: str,
    source_after_replacement: str,
    replacement_offset: int,
    removed_length: int,
) -> tuple[str, ...]:
    if removed_length <= 0:
        return ()
    try:
        before_tree = ast.parse(source_before_replacement)
        after_tree = ast.parse(source_after_replacement)
    except SyntaxError:
        return ()
    removed_span = _span_from_offset(
        source_before_replacement,
        offset=replacement_offset,
        length=removed_length,
    )
    removed_import_names = _module_import_names_in_span(before_tree, removed_span)
    if not removed_import_names:
        return ()
    still_bound = _module_bound_names(after_tree)
    loaded_after = _loaded_names(after_tree)
    missing = removed_import_names - still_bound
    return tuple(sorted(name for name in missing if name in loaded_after))


def removed_module_bound_python_names_still_used(
    *,
    source_before_replacement: str,
    source_after_replacement: str,
    replacement_offset: int,
    removed_length: int,
) -> tuple[str, ...]:
    if removed_length <= 0:
        return ()
    try:
        before_tree = ast.parse(source_before_replacement)
        after_tree = ast.parse(source_after_replacement)
    except SyntaxError:
        return ()
    removed_span = _span_from_offset(
        source_before_replacement,
        offset=replacement_offset,
        length=removed_length,
    )
    removed_names = _module_bound_names_in_span(before_tree, removed_span)
    if not removed_names:
        return ()
    still_bound = _module_bound_names(after_tree)
    loaded_after = _loaded_names(after_tree)
    missing = removed_names - still_bound
    return tuple(sorted(name for name in missing if name in loaded_after))


def introduced_duplicate_python_import_names(
    *,
    source_before_replacement: str,
    source_after_replacement: str,
    replacement_offset: int,
    removed_length: int,
    replacement_length: int,
) -> tuple[str, ...]:
    if replacement_length <= 0:
        return ()
    try:
        before_tree = ast.parse(source_before_replacement)
        after_tree = ast.parse(source_after_replacement)
    except SyntaxError:
        return ()
    removed_span = _span_from_offset(
        source_before_replacement,
        offset=replacement_offset,
        length=removed_length,
    )
    replacement_span = _span_from_offset(
        source_after_replacement,
        offset=replacement_offset,
        length=replacement_length,
    )
    before_removed = _module_import_signatures_in_span(before_tree, removed_span)
    after_replacement = _module_import_signatures_in_span(after_tree, replacement_span)
    after_outside = _module_import_signatures_outside_span(after_tree, replacement_span)
    introduced = after_replacement - before_removed
    duplicates = introduced & after_outside
    return tuple(sorted(_import_signature_name(signature) for signature in duplicates))


def introduced_unknown_private_self_method_calls(
    *,
    source_after_replacement: str,
    replacement_offset: int,
    replacement_length: int,
) -> tuple[str, ...]:
    if replacement_length <= 0:
        return ()
    try:
        tree = ast.parse(source_after_replacement)
    except SyntaxError:
        return ()
    span = _span_from_offset(
        source_after_replacement,
        offset=replacement_offset,
        length=replacement_length,
    )
    missing: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _node_overlaps_span(node, span):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        if not isinstance(func.value, ast.Name) or func.value.id != "self":
            continue
        if not func.attr.startswith("_"):
            continue
        enclosing_class = _innermost_enclosing_class(tree, getattr(node, "lineno", 0))
        if enclosing_class is None:
            continue
        if func.attr not in _class_method_names(enclosing_class):
            missing.add(func.attr)
    return tuple(sorted(missing))


def introduced_unknown_private_self_attribute_loads(
    *,
    source_after_replacement: str,
    replacement_offset: int,
    replacement_length: int,
) -> tuple[str, ...]:
    if replacement_length <= 0:
        return ()
    try:
        tree = ast.parse(source_after_replacement)
    except SyntaxError:
        return ()
    span = _span_from_offset(
        source_after_replacement,
        offset=replacement_offset,
        length=replacement_length,
    )
    missing: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute) or not _node_overlaps_span(node, span):
            continue
        if not isinstance(node.value, ast.Name) or node.value.id != "self":
            continue
        if not node.attr.startswith("_") or isinstance(node.ctx, (ast.Store, ast.Del)):
            continue
        enclosing_class = _innermost_enclosing_class(tree, getattr(node, "lineno", 0))
        if enclosing_class is None:
            continue
        if node.attr not in _class_private_member_names(enclosing_class):
            missing.add(node.attr)
    return tuple(sorted(missing))


def _span_from_offset(source: str, *, offset: int, length: int) -> ReplacementSpan:
    start_line = source.count("\n", 0, offset) + 1
    replacement_text = source[offset : offset + length]
    end_line = start_line + replacement_text.count("\n")
    return ReplacementSpan(start_line=start_line, end_line=max(start_line, end_line))


def _loaded_names_in_span(tree: ast.AST, span: ReplacementSpan) -> set[str]:
    return {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
        and isinstance(node.ctx, ast.Load)
        and _node_overlaps_span(node, span)
    }


def _loaded_names(tree: ast.AST) -> set[str]:
    return {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }


def _module_import_names_in_span(tree: ast.Module, span: ReplacementSpan) -> set[str]:
    names: set[str] = set()
    for statement in tree.body:
        if not isinstance(statement, (ast.Import, ast.ImportFrom)):
            continue
        if _node_overlaps_span(statement, span):
            names.update(_import_bound_names(statement))
    return names


def _module_bound_names_in_span(tree: ast.Module, span: ReplacementSpan) -> set[str]:
    names: set[str] = set()
    for statement in tree.body:
        if _node_overlaps_span(statement, span):
            names.update(_bound_names_from_statement(statement))
    return names


def _module_import_signatures_in_span(
    tree: ast.Module,
    span: ReplacementSpan,
) -> set[tuple[str, str, str, str]]:
    signatures: set[tuple[str, str, str, str]] = set()
    for statement in tree.body:
        if not isinstance(statement, (ast.Import, ast.ImportFrom)):
            continue
        if _node_overlaps_span(statement, span):
            signatures.update(_import_signatures(statement))
    return signatures


def _module_import_signatures_outside_span(
    tree: ast.Module,
    span: ReplacementSpan,
) -> set[tuple[str, str, str, str]]:
    signatures: set[tuple[str, str, str, str]] = set()
    for statement in tree.body:
        if not isinstance(statement, (ast.Import, ast.ImportFrom)):
            continue
        if not _node_overlaps_span(statement, span):
            signatures.update(_import_signatures(statement))
    return signatures


def _bound_names_in_span(tree: ast.AST, span: ReplacementSpan) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if not _node_overlaps_span(node, span):
            continue
        names.update(_bound_names_from_node(node))
    return names


def _available_names_at_span(tree: ast.Module, span: ReplacementSpan) -> set[str]:
    names = set(dir(builtins)) | {
        "__builtins__",
        "__file__",
        "__loader__",
        "__name__",
        "__package__",
        "__spec__",
    }
    names.update(_module_bound_names(tree))
    for scope in _enclosing_scopes(tree, span.start_line):
        if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.update(_argument_names(scope.args))
            names.update(_bound_names_before_line(scope.body, span.start_line))
        elif isinstance(scope, ast.Lambda):
            names.update(_argument_names(scope.args))
        elif isinstance(scope, ast.ClassDef):
            names.update(_bound_names_before_line(scope.body, span.start_line))
    return names


def _module_bound_names(tree: ast.Module) -> set[str]:
    return _bound_names_before_line(tree.body, line=10**9)


def _enclosing_scopes(tree: ast.AST, line: int) -> list[ast.AST]:
    scopes: list[ast.AST] = []
    for node in ast.walk(tree):
        if not isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef),
        ):
            continue
        if _line_inside_node(node, line):
            scopes.append(node)
    scopes.sort(key=lambda node: (getattr(node, "lineno", 0), -(getattr(node, "end_lineno", 0))))
    return scopes


def _innermost_enclosing_class(tree: ast.AST, line: int) -> ast.ClassDef | None:
    classes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and _line_inside_node(node, line)
    ]
    if not classes:
        return None
    classes.sort(key=lambda node: (getattr(node, "lineno", 0), -(getattr(node, "end_lineno", 0))))
    return classes[-1]


def _class_method_names(node: ast.ClassDef) -> set[str]:
    return {
        statement.name
        for statement in node.body
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _class_private_member_names(node: ast.ClassDef) -> set[str]:
    names = _class_method_names(node)
    for child in ast.walk(node):
        if not isinstance(child, ast.Attribute):
            continue
        if not isinstance(child.value, ast.Name) or child.value.id != "self":
            continue
        if child.attr.startswith("_") and isinstance(child.ctx, ast.Store):
            names.add(child.attr)
    return names


def _bound_names_before_line(statements: list[ast.stmt], line: int) -> set[str]:
    names: set[str] = set()
    for statement in statements:
        if getattr(statement, "lineno", line) >= line:
            continue
        names.update(_bound_names_from_statement(statement))
    return names


def _bound_names_from_statement(statement: ast.stmt) -> set[str]:
    if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return {statement.name}
    if isinstance(statement, (ast.Import, ast.ImportFrom)):
        return _import_bound_names(statement)
    if isinstance(statement, ast.If):
        return _definitely_bound_names_from_if(statement)
    return _bound_names_from_node(statement)


def _definitely_bound_names_from_if(statement: ast.If) -> set[str]:
    if not statement.orelse:
        return set()
    return _bound_names_from_statements(statement.body) & _bound_names_from_statements(
        statement.orelse
    )


def _bound_names_from_statements(statements: list[ast.stmt]) -> set[str]:
    names: set[str] = set()
    for statement in statements:
        names.update(_bound_names_from_statement(statement))
    return names


def _bound_names_from_node(node: ast.AST) -> set[str]:
    names: set[str] = set()
    if isinstance(node, ast.ExceptHandler) and isinstance(node.name, str):
        names.add(node.name)
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        names.add(node.name)
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        names.update(_import_bound_names(node))
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and isinstance(child.ctx, (ast.Store, ast.Param)):
            names.add(child.id)
        elif isinstance(child, ast.arg):
            names.add(child.arg)
    return names


def _import_bound_names(node: ast.Import | ast.ImportFrom) -> set[str]:
    names: set[str] = set()
    for alias in node.names:
        if alias.asname:
            names.add(alias.asname)
            continue
        names.add(alias.name.split(".", 1)[0])
    return names


def _import_signatures(node: ast.Import | ast.ImportFrom) -> set[tuple[str, str, str, str]]:
    signatures: set[tuple[str, str, str, str]] = set()
    if isinstance(node, ast.Import):
        for alias in node.names:
            signatures.add(("import", alias.name, "", alias.asname or ""))
        return signatures
    module = node.module or ""
    for alias in node.names:
        signatures.add(("from", module, alias.name, alias.asname or ""))
    return signatures


def _import_signature_name(signature: tuple[str, str, str, str]) -> str:
    import_type, module, imported_name, alias = signature
    if alias:
        return alias
    if import_type == "import":
        return module.split(".", 1)[0]
    return imported_name


def _argument_names(arguments: ast.arguments) -> set[str]:
    args = [
        *arguments.posonlyargs,
        *arguments.args,
        *arguments.kwonlyargs,
    ]
    names = {arg.arg for arg in args}
    if arguments.vararg is not None:
        names.add(arguments.vararg.arg)
    if arguments.kwarg is not None:
        names.add(arguments.kwarg.arg)
    return names


def _node_overlaps_span(node: ast.AST, span: ReplacementSpan) -> bool:
    node_start = getattr(node, "lineno", None)
    node_end = getattr(node, "end_lineno", node_start)
    if node_start is None or node_end is None:
        return False
    return node_start <= span.end_line and node_end >= span.start_line


def _line_inside_node(node: ast.AST, line: int) -> bool:
    node_start = getattr(node, "lineno", None)
    node_end = getattr(node, "end_lineno", None)
    if node_start is None or node_end is None:
        return False
    return node_start <= line <= node_end
