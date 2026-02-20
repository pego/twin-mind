"""Entity extraction and knowledge graph queries for twin-mind."""

import ast
import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any, DefaultDict, Dict, List, Optional, Sequence, Set, Tuple

from twin_mind.config import parse_size
from twin_mind.entity_extractors import (
    EntityExtractionResult,
    EntityExtractor,
    EntityExtractorRegistry,
)
from twin_mind.fs import FileLock, get_entities_db_path
from twin_mind.js_oxc import extract_javascript_entities_with_oxc

_EXTRACTOR_REGISTRY = EntityExtractorRegistry()


class _PythonEntityVisitor(ast.NodeVisitor):
    """Extract entities and relationships from Python AST."""

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self.module_name = _module_name_from_path(file_path)
        self.is_package_init = Path(file_path).stem == "__init__"
        self.entities: List[Dict[str, Any]] = []
        self.relations: List[Dict[str, Any]] = []
        self._scope_stack: List[str] = [self.module_name]
        self._scope_kind_stack: List[str] = ["module"]

        self.entities.append(
            {
                "file_path": self.file_path,
                "name": self.module_name,
                "qualname": self.module_name,
                "kind": "module",
                "line": 1,
            }
        )

    def _current_scope(self) -> str:
        return self._scope_stack[-1]

    def _current_scope_kind(self) -> str:
        return self._scope_kind_stack[-1]

    def _push_scope(self, qualname: str, kind: str) -> None:
        self._scope_stack.append(qualname)
        self._scope_kind_stack.append(kind)

    def _pop_scope(self) -> None:
        self._scope_stack.pop()
        self._scope_kind_stack.pop()

    def _add_relation(self, src: str, dst: str, relation: str, line: int) -> None:
        if not src or not dst:
            return
        self.relations.append(
            {
                "file_path": self.file_path,
                "src_qualname": src,
                "dst_name": dst,
                "relation": relation,
                "line": line,
            }
        )

    def _add_entity(self, name: str, kind: str, line: int) -> str:
        parent = self._current_scope()
        qualname = f"{parent}.{name}"
        self.entities.append(
            {
                "file_path": self.file_path,
                "name": name,
                "qualname": qualname,
                "kind": kind,
                "line": line,
            }
        )
        self._add_relation(parent, qualname, "defines", line)
        return qualname

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        qualname = self._add_entity(node.name, "class", getattr(node, "lineno", 0))

        for base in node.bases:
            base_name = _expr_to_name(base)
            if base_name:
                self._add_relation(qualname, base_name, "inherits", getattr(node, "lineno", 0))

        self._push_scope(qualname, "class")
        self.generic_visit(node)
        self._pop_scope()
        return None

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        kind = "method" if self._current_scope_kind() == "class" else "function"
        qualname = self._add_entity(node.name, kind, getattr(node, "lineno", 0))
        self._push_scope(qualname, kind)
        self.generic_visit(node)
        self._pop_scope()
        return None

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        kind = "method" if self._current_scope_kind() == "class" else "function"
        qualname = self._add_entity(node.name, kind, getattr(node, "lineno", 0))
        self._push_scope(qualname, kind)
        self.generic_visit(node)
        self._pop_scope()
        return None

    def visit_Call(self, node: ast.Call) -> Any:
        callee = _expr_to_name(node.func)
        if callee:
            self._add_relation(
                self._current_scope(),
                callee,
                "calls",
                getattr(node, "lineno", 0),
            )
        self.generic_visit(node)
        return None

    def visit_Import(self, node: ast.Import) -> Any:
        src = self._current_scope()
        for alias in node.names:
            imported = alias.name.strip()
            if imported:
                line = getattr(node, "lineno", 0)
                self._add_relation(src, imported, "imports", line)

                local_name = alias.asname.strip() if alias.asname else ""
                target = imported
                if not local_name and "." in imported:
                    first = imported.split(".", 1)[0]
                    local_name = first
                    target = first
                if local_name:
                    self._add_relation(src, f"{local_name}={target}", "imports_alias", line)
        self.generic_visit(node)
        return None

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
        src = self._current_scope()
        module = _resolve_import_module(
            module_name=self.module_name,
            module=(node.module or "").strip(),
            level=int(getattr(node, "level", 0) or 0),
            is_package_init=self.is_package_init,
        )
        line = getattr(node, "lineno", 0)
        for alias in node.names:
            leaf = alias.name.strip()
            if not leaf or leaf == "*":
                continue
            imported = f"{module}.{leaf}" if module else leaf
            self._add_relation(src, imported, "imports", line)
            if alias.asname:
                self._add_relation(src, f"{alias.asname.strip()}={imported}", "imports_alias", line)
        self.generic_visit(node)
        return None


def _module_name_from_path(file_path: str) -> str:
    normalized = file_path.replace("\\", "/").strip("/")
    path = Path(normalized)
    stemmed = path.with_suffix("")
    parts = list(stemmed.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    if not parts:
        return "module"
    return ".".join(parts)


def _expr_to_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _expr_to_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return _expr_to_name(node.func)
    if isinstance(node, ast.Subscript):
        return _expr_to_name(node.value)
    return ""


def _resolve_import_module(
    module_name: str, module: str, level: int, is_package_init: bool = False
) -> str:
    module = module.strip()
    if level <= 0:
        return module

    if is_package_init:
        base_package = module_name
    else:
        base_package = module_name.rsplit(".", 1)[0] if "." in module_name else ""

    parts = [part for part in base_package.split(".") if part]
    climb = max(level - 1, 0)
    if climb >= len(parts):
        parts = []
    elif climb:
        parts = parts[: -climb]

    if module:
        parts.extend(part for part in module.split(".") if part)
    return ".".join(parts)


def _parse_import_alias(raw: str) -> Tuple[str, str]:
    value = raw.strip()
    if "=" not in value:
        return "", ""
    alias, target = value.split("=", 1)
    alias = alias.strip().lower()
    target = target.strip().lower()
    if not alias or not target:
        return "", ""
    return alias, target


def _resolve_js_import_symbol(module_name: str, import_path: str) -> str:
    raw = import_path.strip().replace("\\", "/")
    if not raw:
        return ""

    base, _ = re.subn(r"\.(js|jsx|mjs|cjs|ts|tsx)$", "", raw, flags=re.IGNORECASE)
    path_value = base
    if path_value.startswith("."):
        current_parts = [part for part in module_name.split(".")[:-1] if part]
        for part in path_value.split("/"):
            if not part or part == ".":
                continue
            if part == "..":
                if current_parts:
                    current_parts.pop()
                continue
            current_parts.append(part)
        return ".".join(current_parts)

    return path_value.replace("/", ".")


def _line_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, max(offset, 0)) + 1


def _neutralize_js_content(content: str) -> str:
    """Replace JS/TS strings and comments with spaces while preserving offsets/newlines."""
    chars = list(content)
    out = chars[:]
    i = 0
    n = len(chars)
    state = "code"
    quote = ""

    while i < n:
        c = chars[i]
        nxt = chars[i + 1] if i + 1 < n else ""

        if state == "code":
            if c == "/" and nxt == "/":
                out[i] = " "
                out[i + 1] = " "
                i += 2
                state = "line_comment"
                continue
            if c == "/" and nxt == "*":
                out[i] = " "
                out[i + 1] = " "
                i += 2
                state = "block_comment"
                continue
            if c in ("'", '"', "`"):
                quote = c
                out[i] = " "
                i += 1
                state = "string"
                continue
            i += 1
            continue

        if state == "line_comment":
            if c == "\n":
                i += 1
                state = "code"
                continue
            out[i] = " "
            i += 1
            continue

        if state == "block_comment":
            if c == "*" and nxt == "/":
                out[i] = " "
                out[i + 1] = " "
                i += 2
                state = "code"
                continue
            if c != "\n":
                out[i] = " "
            i += 1
            continue

        if state == "string":
            if c == "\\" and i + 1 < n:
                if out[i] != "\n":
                    out[i] = " "
                if out[i + 1] != "\n":
                    out[i + 1] = " "
                i += 2
                continue
            if c == quote:
                out[i] = " "
                i += 1
                state = "code"
                continue
            if c != "\n":
                out[i] = " "
            i += 1
            continue

    return "".join(out)


def _find_matching_brace(text: str, open_index: int) -> Optional[int]:
    if open_index < 0 or open_index >= len(text) or text[open_index] != "{":
        return None
    depth = 1
    idx = open_index + 1
    while idx < len(text):
        c = text[idx]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return idx
        idx += 1
    return None


def _add_js_import_relations(
    module_scope: str,
    line: int,
    module_symbol: str,
    specifier: str,
    add_relation: Any,
) -> None:
    spec = specifier.strip()
    if not module_symbol:
        return

    add_relation(module_scope, module_symbol, "imports", line)

    def add_alias(local_name: str, target: str) -> None:
        alias = local_name.strip()
        dst = target.strip()
        if alias and dst:
            add_relation(module_scope, f"{alias}={dst}", "imports_alias", line)

    star_match = re.search(r"\*\s+as\s+([A-Za-z_$][\w$]*)", spec)
    if star_match:
        add_alias(star_match.group(1), module_symbol)

    named_match = re.search(r"\{([^}]*)\}", spec, flags=re.DOTALL)
    if named_match:
        for raw_item in named_match.group(1).split(","):
            token = raw_item.strip()
            if not token:
                continue
            if token.startswith("type "):
                token = token[5:].strip()
            if not token:
                continue
            if " as " in token:
                imported_name, alias_name = [part.strip() for part in token.split(" as ", 1)]
            elif ":" in token:
                imported_name, alias_name = [part.strip() for part in token.split(":", 1)]
            else:
                imported_name = token
                alias_name = token
            if not imported_name:
                continue
            full_target = f"{module_symbol}.{imported_name}"
            add_relation(module_scope, full_target, "imports", line)
            add_alias(alias_name or imported_name, full_target)

    default_part = spec
    if "{" in default_part:
        default_part = default_part.split("{", 1)[0].strip().rstrip(",")
    if "*" in default_part:
        default_part = ""
    default_name = default_part.strip()
    if default_name and default_name != "type":
        add_alias(default_name, module_symbol)


def _collect_js_calls(body_text: str) -> List[Tuple[str, int]]:
    calls: List[Tuple[str, int]] = []
    call_pattern = re.compile(r"(?<![\w$.])([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\s*\(")
    skip = {
        "if",
        "for",
        "while",
        "switch",
        "catch",
        "return",
        "typeof",
        "await",
        "function",
        "import",
    }
    for match in call_pattern.finditer(body_text):
        callee = match.group(1)
        if callee in skip:
            continue
        calls.append((callee, match.start()))
    return calls


def _extract_javascript_entities_fallback(file_path: str, content: str) -> EntityExtractionResult:
    """Extract entities + relations for JavaScript/TypeScript files."""
    neutral = _neutralize_js_content(content)
    module_name = _module_name_from_path(file_path)
    entities: List[Dict[str, Any]] = [
        {
            "file_path": file_path,
            "name": module_name,
            "qualname": module_name,
            "kind": "module",
            "line": 1,
        }
    ]
    relations: List[Dict[str, Any]] = []

    def add_relation(src: str, dst: str, relation: str, line: int) -> None:
        if not src or not dst:
            return
        relations.append(
            {
                "file_path": file_path,
                "src_qualname": src,
                "dst_name": dst,
                "relation": relation,
                "line": line,
            }
        )

    def add_entity(parent: str, name: str, kind: str, line: int) -> str:
        qualname = f"{parent}.{name}"
        entities.append(
            {
                "file_path": file_path,
                "name": name,
                "qualname": qualname,
                "kind": kind,
                "line": line,
            }
        )
        add_relation(parent, qualname, "defines", line)
        return qualname

    module_scope = module_name
    entity_keys: Set[Tuple[str, str]] = {(module_scope, "module")}
    scoped_blocks: List[Tuple[str, int, int]] = []

    import_pattern = re.compile(
        r"import\s+([\s\S]*?)\s+from\s+['\"]([^'\"]+)['\"]\s*;?",
        flags=re.MULTILINE,
    )
    for match in import_pattern.finditer(content):
        specifier = match.group(1).strip()
        import_path = match.group(2).strip()
        module_symbol = _resolve_js_import_symbol(module_name, import_path)
        line = _line_for_offset(content, match.start())
        _add_js_import_relations(module_scope, line, module_symbol, specifier, add_relation)

    side_effect_import_pattern = re.compile(
        r"(?m)^\s*import\s+['\"]([^'\"]+)['\"]\s*;?",
    )
    for match in side_effect_import_pattern.finditer(content):
        import_path = match.group(1).strip()
        module_symbol = _resolve_js_import_symbol(module_name, import_path)
        if module_symbol:
            add_relation(module_scope, module_symbol, "imports", _line_for_offset(content, match.start()))

    require_pattern = re.compile(
        r"(?m)^\s*(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*require\(\s*['\"]([^'\"]+)['\"]\s*\)\s*;?",
    )
    for match in require_pattern.finditer(content):
        local_name = match.group(1)
        import_path = match.group(2).strip()
        module_symbol = _resolve_js_import_symbol(module_name, import_path)
        line = _line_for_offset(content, match.start())
        if module_symbol:
            add_relation(module_scope, module_symbol, "imports", line)
            add_relation(module_scope, f"{local_name}={module_symbol}", "imports_alias", line)

    require_destructured_pattern = re.compile(
        r"(?m)^\s*(?:const|let|var)\s*\{([^}]+)\}\s*=\s*require\(\s*['\"]([^'\"]+)['\"]\s*\)\s*;?",
    )
    for match in require_destructured_pattern.finditer(content):
        import_spec = match.group(1).strip()
        import_path = match.group(2).strip()
        module_symbol = _resolve_js_import_symbol(module_name, import_path)
        line = _line_for_offset(content, match.start())
        if not module_symbol:
            continue
        add_relation(module_scope, module_symbol, "imports", line)
        for item in import_spec.split(","):
            token = item.strip()
            if not token:
                continue
            if ":" in token:
                imported_name, alias_name = [part.strip() for part in token.split(":", 1)]
            else:
                imported_name = token
                alias_name = token
            if not imported_name:
                continue
            full_target = f"{module_symbol}.{imported_name}"
            add_relation(module_scope, full_target, "imports", line)
            add_relation(module_scope, f"{alias_name}={full_target}", "imports_alias", line)

    class_pattern = re.compile(
        r"\b(?:export\s+)?(?:default\s+)?class\s+([A-Za-z_$][\w$]*)"
        r"(?:\s+extends\s+([A-Za-z_$][\w$.]*))?\s*\{"
    )
    method_pattern = re.compile(
        r"(?m)^\s*(?:async\s+)?([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{"
    )
    method_skip = {"if", "for", "while", "switch", "catch"}

    for match in class_pattern.finditer(neutral):
        class_name = match.group(1)
        base_name = (match.group(2) or "").strip()
        line = _line_for_offset(content, match.start())
        class_qualname = f"{module_scope}.{class_name}"
        if (class_qualname, "class") not in entity_keys:
            add_entity(module_scope, class_name, "class", line)
            entity_keys.add((class_qualname, "class"))
        if base_name:
            add_relation(class_qualname, base_name, "inherits", line)

        class_open = match.end() - 1
        class_close = _find_matching_brace(neutral, class_open)
        if class_close is None:
            continue

        body_start = class_open + 1
        body_end = class_close
        class_body = neutral[body_start:body_end]
        for method_match in method_pattern.finditer(class_body):
            method_name = method_match.group(1)
            if method_name in method_skip:
                continue
            abs_start = body_start + method_match.start()
            method_line = _line_for_offset(content, abs_start)
            method_qual = f"{class_qualname}.{method_name}"
            if (method_qual, "method") not in entity_keys:
                add_entity(class_qualname, method_name, "method", method_line)
                entity_keys.add((method_qual, "method"))

            method_open = body_start + method_match.end() - 1
            method_close = _find_matching_brace(neutral, method_open)
            if method_close is None or method_close > body_end:
                continue
            scoped_blocks.append((method_qual, method_open + 1, method_close))

    depth_prefix = [0] * (len(neutral) + 1)
    depth = 0
    for idx, char in enumerate(neutral):
        if char == "{":
            depth += 1
        elif char == "}":
            depth = max(0, depth - 1)
        depth_prefix[idx + 1] = depth

    function_patterns = [
        re.compile(
            r"(?m)^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+"
            r"([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{"
        ),
        re.compile(
            r"(?m)^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*"
            r"(?:async\s+)?function\b[^{]*\{"
        ),
        re.compile(
            r"(?m)^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*"
            r"(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>\s*\{"
        ),
    ]

    for pattern in function_patterns:
        for match in pattern.finditer(neutral):
            if depth_prefix[match.start()] != 0:
                continue
            function_name = match.group(1)
            function_qual = f"{module_scope}.{function_name}"
            line = _line_for_offset(content, match.start())
            if (function_qual, "function") not in entity_keys:
                add_entity(module_scope, function_name, "function", line)
                entity_keys.add((function_qual, "function"))

            function_open = match.end() - 1
            function_close = _find_matching_brace(neutral, function_open)
            if function_close is None:
                continue
            scoped_blocks.append((function_qual, function_open + 1, function_close))

    for scope_qualname, body_start, body_end in scoped_blocks:
        body = neutral[body_start:body_end]
        for callee, rel_offset in _collect_js_calls(body):
            line = _line_for_offset(content, body_start + rel_offset)
            add_relation(scope_qualname, callee, "calls", line)

    return entities, relations


def extract_javascript_entities(file_path: str, content: str) -> EntityExtractionResult:
    """Extract JS/TS entities, preferring oxc-parser when available."""
    extracted = extract_javascript_entities_with_oxc(file_path, content)
    if extracted is not None:
        return extracted
    return _extract_javascript_entities_fallback(file_path, content)


def _table_columns(conn: sqlite3.Connection, table: str) -> Set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    columns: Set[str] = set()
    for row in rows:
        if isinstance(row, sqlite3.Row):
            columns.add(str(row["name"]))
        elif isinstance(row, (list, tuple)) and len(row) > 1:
            columns.add(str(row[1]))
    return columns


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl_suffix: str) -> bool:
    if column in _table_columns(conn, table):
        return False
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_suffix}")
    return True


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL,
            name TEXT NOT NULL,
            qualname TEXT NOT NULL,
            kind TEXT NOT NULL,
            line INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS relations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL,
            src_qualname TEXT NOT NULL,
            dst_name TEXT NOT NULL,
            relation TEXT NOT NULL,
            line INTEGER NOT NULL DEFAULT 0,
            src_entity_id INTEGER,
            dst_entity_id INTEGER,
            resolved INTEGER NOT NULL DEFAULT 0,
            confidence REAL NOT NULL DEFAULT 0.0
        )
        """
    )
    added_link_columns = False
    added_link_columns |= _ensure_column(conn, "relations", "src_entity_id", "INTEGER")
    added_link_columns |= _ensure_column(conn, "relations", "dst_entity_id", "INTEGER")
    added_link_columns |= _ensure_column(conn, "relations", "resolved", "INTEGER NOT NULL DEFAULT 0")
    added_link_columns |= _ensure_column(conn, "relations", "confidence", "REAL NOT NULL DEFAULT 0.0")
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_entities_unique
        ON entities(file_path, qualname, kind)
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_relations_unique
        ON relations(file_path, src_qualname, dst_name, relation, line)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_entities_name
        ON entities(name)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_entities_qualname
        ON entities(qualname)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_relations_lookup
        ON relations(relation, dst_name)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_relations_src_entity
        ON relations(src_entity_id)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_relations_dst_entity
        ON relations(dst_entity_id)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_relations_resolution
        ON relations(relation, resolved, confidence)
        """
    )
    if added_link_columns:
        _resolve_relations(conn)
        _derive_rich_relations(conn)
    conn.commit()


def _connect() -> sqlite3.Connection:
    db_path = get_entities_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    return conn


def _clear_file_graph(conn: sqlite3.Connection, file_path: str) -> None:
    conn.execute("DELETE FROM relations WHERE file_path = ?", (file_path,))
    conn.execute("DELETE FROM entities WHERE file_path = ?", (file_path,))


def extract_python_entities(file_path: str, content: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Extract entities + relations for a Python source file."""
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return [], []

    visitor = _PythonEntityVisitor(file_path)
    visitor.visit(tree)
    return visitor.entities, visitor.relations


def _register_default_extractors() -> None:
    """Register built-in language extractors."""
    if _EXTRACTOR_REGISTRY.supports_path("placeholder.py"):
        return
    _EXTRACTOR_REGISTRY.register(
        EntityExtractor(
            language="python",
            extensions=(".py",),
            extract=extract_python_entities,
        )
    )
    _EXTRACTOR_REGISTRY.register(
        EntityExtractor(
            language="javascript",
            extensions=(".js", ".jsx", ".mjs", ".cjs"),
            extract=extract_javascript_entities,
        )
    )
    _EXTRACTOR_REGISTRY.register(
        EntityExtractor(
            language="typescript",
            extensions=(".ts", ".tsx"),
            extract=extract_javascript_entities,
        )
    )


def extract_entities(file_path: str, content: str) -> EntityExtractionResult:
    """Extract entities + relations for a supported file path."""
    return _EXTRACTOR_REGISTRY.extract_for_path(file_path, content)


def supported_entity_languages() -> List[str]:
    """Return currently supported entity extraction languages."""
    return _EXTRACTOR_REGISTRY.supported_languages()


_register_default_extractors()


def _index_file_content(
    conn: sqlite3.Connection, file_path: str, content: str
) -> Tuple[int, int]:
    entities, relations = extract_entities(file_path, content)
    if not entities and not relations:
        return 0, 0

    entity_rows = [
        (
            entity["file_path"],
            entity["name"],
            entity["qualname"],
            entity["kind"],
            int(entity.get("line", 0)),
        )
        for entity in entities
    ]
    relation_rows = [
        (
            relation["file_path"],
            relation["src_qualname"],
            relation["dst_name"],
            relation["relation"],
            int(relation.get("line", 0)),
        )
        for relation in relations
    ]

    conn.executemany(
        """
        INSERT OR IGNORE INTO entities(file_path, name, qualname, kind, line)
        VALUES (?, ?, ?, ?, ?)
        """,
        entity_rows,
    )
    conn.executemany(
        """
        INSERT OR IGNORE INTO relations(file_path, src_qualname, dst_name, relation, line)
        VALUES (?, ?, ?, ?, ?)
        """,
        relation_rows,
    )
    return len(entity_rows), len(relation_rows)


def _unique_ints(values: Sequence[int]) -> List[int]:
    return list(dict.fromkeys(values))


def _scope_chain(src_qualname: str, module_name: str) -> List[str]:
    scopes: List[str] = []
    raw = src_qualname.strip()
    if raw:
        parts = raw.split(".")
        for idx in range(len(parts), 0, -1):
            scopes.append(".".join(parts[:idx]).lower())
    module_lower = module_name.strip().lower()
    if module_lower and module_lower not in scopes:
        scopes.append(module_lower)
    return scopes


def _candidate_ids_for_symbol(
    symbol: str,
    entity_id_by_qualname: Dict[str, int],
    entity_ids_by_suffix: Dict[str, List[int]],
) -> List[int]:
    normalized = symbol.strip().lower()
    if not normalized:
        return []
    direct = entity_id_by_qualname.get(normalized)
    if direct is not None:
        return [direct]
    return _unique_ints(entity_ids_by_suffix.get(normalized, []))


def _pick_best_candidate(candidates: Dict[int, float]) -> Tuple[Optional[int], float]:
    if not candidates:
        return None, 0.0
    if len(candidates) == 1:
        entity_id, confidence = next(iter(candidates.items()))
        return entity_id, confidence
    ranked = sorted(candidates.items(), key=lambda item: item[1], reverse=True)
    top_id, top_score = ranked[0]
    _, second_score = ranked[1]
    if top_score - second_score >= 0.15:
        return top_id, top_score
    return None, 0.0


def _resolve_relation_destination(
    relation_kind: str,
    file_path: str,
    src_qualname: str,
    dst_name: str,
    src_entity_id: Optional[int],
    entity_id_by_qualname: Dict[str, int],
    entity_ids_by_suffix: Dict[str, List[int]],
    entity_ids_by_name: Dict[str, List[int]],
    entity_ids_by_module_and_name: Dict[Tuple[str, str], List[int]],
    entity_ids_by_class_and_name: Dict[Tuple[str, str], List[int]],
    entity_kind_by_id: Dict[int, str],
    entity_qualname_by_id: Dict[int, str],
    imports_by_scope: Dict[str, Dict[str, Set[str]]],
) -> Tuple[Optional[int], float]:
    dst = dst_name.strip().lower()
    if not dst:
        return None, 0.0

    module_name = _module_name_from_path(file_path).lower()
    src_kind = entity_kind_by_id.get(src_entity_id or -1, "")
    src_qual = entity_qualname_by_id.get(src_entity_id or -1, src_qualname).lower()
    src_class_qual = ""
    if src_kind == "method" and "." in src_qual:
        src_class_qual = src_qual.rsplit(".", 1)[0]
    elif src_kind == "class":
        src_class_qual = src_qual

    candidates: Dict[int, float] = {}

    def add_candidates(ids: Sequence[int], confidence: float) -> None:
        for entity_id in ids:
            previous = candidates.get(entity_id, 0.0)
            if confidence > previous:
                candidates[entity_id] = confidence

    direct = entity_id_by_qualname.get(dst)
    if direct is not None:
        add_candidates([direct], 1.0)

    if relation_kind == "defines":
        return _pick_best_candidate(candidates)

    if dst.startswith("self.") or dst.startswith("cls."):
        _, _, member = dst.partition(".")
        if src_class_qual and member:
            scoped_symbol = f"{src_class_qual}.{member}"
            add_candidates(
                _candidate_ids_for_symbol(scoped_symbol, entity_id_by_qualname, entity_ids_by_suffix),
                0.98,
            )

    is_dotted = "." in dst
    if not is_dotted:
        if src_class_qual:
            class_ids = _unique_ints(entity_ids_by_class_and_name.get((src_class_qual, dst), []))
            if len(class_ids) == 1:
                add_candidates(class_ids, 0.97)

        module_ids = _unique_ints(entity_ids_by_module_and_name.get((module_name, dst), []))
        if len(module_ids) == 1:
            add_candidates(module_ids, 0.93)
    else:
        module_symbol = f"{module_name}.{dst}" if module_name else dst
        add_candidates(
            _candidate_ids_for_symbol(module_symbol, entity_id_by_qualname, entity_ids_by_suffix),
            0.88,
        )

    scopes = _scope_chain(src_qualname, module_name)
    for depth, scope in enumerate(scopes):
        scoped_imports = imports_by_scope.get(scope, {})
        if not scoped_imports:
            continue
        base_confidence = max(0.84, 0.95 - (0.02 * depth))
        if not is_dotted:
            for imported in scoped_imports.get(dst, set()):
                add_candidates(
                    _candidate_ids_for_symbol(
                        imported,
                        entity_id_by_qualname,
                        entity_ids_by_suffix,
                    ),
                    base_confidence,
                )
            continue

        prefix, _, suffix = dst.partition(".")
        for imported in scoped_imports.get(prefix, set()):
            composed = f"{imported}.{suffix}" if suffix else imported
            add_candidates(
                _candidate_ids_for_symbol(
                    composed,
                    entity_id_by_qualname,
                    entity_ids_by_suffix,
                ),
                max(0.0, base_confidence - 0.01),
            )

    suffix_ids = _unique_ints(entity_ids_by_suffix.get(dst, []))
    if len(suffix_ids) == 1:
        add_candidates(suffix_ids, 0.86)

    name_ids = _unique_ints(entity_ids_by_name.get(dst, []))
    if len(name_ids) == 1:
        add_candidates(name_ids, 0.80)

    return _pick_best_candidate(candidates)


def _resolve_relations(conn: sqlite3.Connection) -> None:
    required_columns = {"src_entity_id", "dst_entity_id", "resolved", "confidence"}
    if not required_columns.issubset(_table_columns(conn, "relations")):
        return

    relation_rows = conn.execute(
        """
        SELECT id, file_path, src_qualname, dst_name, relation
        FROM relations
        """
    ).fetchall()
    if not relation_rows:
        return

    entity_rows = conn.execute(
        """
        SELECT id, file_path, name, qualname, kind
        FROM entities
        """
    ).fetchall()
    if not entity_rows:
        conn.execute(
            """
            UPDATE relations
            SET src_entity_id = NULL, dst_entity_id = NULL, resolved = 0, confidence = 0.0
            """
        )
        return

    entity_id_by_qualname: Dict[str, int] = {}
    entity_id_by_file_qualname: Dict[Tuple[str, str], int] = {}
    entity_kind_by_id: Dict[int, str] = {}
    entity_qualname_by_id: Dict[int, str] = {}
    entity_ids_by_name: DefaultDict[str, List[int]] = defaultdict(list)
    entity_ids_by_module_and_name: DefaultDict[Tuple[str, str], List[int]] = defaultdict(list)
    entity_ids_by_class_and_name: DefaultDict[Tuple[str, str], List[int]] = defaultdict(list)
    entity_ids_by_suffix: DefaultDict[str, List[int]] = defaultdict(list)

    for row in entity_rows:
        entity_id = int(row["id"])
        file_path = str(row["file_path"])
        qualname = str(row["qualname"]).strip()
        name = str(row["name"]).strip()
        kind = str(row["kind"]).strip()

        qualname_lower = qualname.lower()
        name_lower = name.lower()
        module_name = _module_name_from_path(file_path).lower()

        entity_id_by_qualname[qualname_lower] = entity_id
        entity_id_by_file_qualname[(file_path, qualname_lower)] = entity_id
        entity_kind_by_id[entity_id] = kind
        entity_qualname_by_id[entity_id] = qualname
        entity_ids_by_name[name_lower].append(entity_id)
        entity_ids_by_module_and_name[(module_name, name_lower)].append(entity_id)

        if kind == "method" and "." in qualname_lower:
            class_qualname = qualname_lower.rsplit(".", 1)[0]
            entity_ids_by_class_and_name[(class_qualname, name_lower)].append(entity_id)

        parts = qualname_lower.split(".")
        for idx in range(len(parts)):
            suffix = ".".join(parts[idx:])
            entity_ids_by_suffix[suffix].append(entity_id)

    imports_by_scope: Dict[str, Dict[str, Set[str]]] = {}
    import_rows = conn.execute(
        """
        SELECT src_qualname, dst_name, relation
        FROM relations
        WHERE relation IN ('imports', 'imports_alias')
        """
    ).fetchall()
    for row in import_rows:
        scope = str(row["src_qualname"]).strip().lower()
        raw_value = str(row["dst_name"]).strip()
        relation_kind = str(row["relation"]).strip().lower()
        if not scope or not raw_value:
            continue

        scoped = imports_by_scope.setdefault(scope, {})
        if relation_kind == "imports_alias":
            alias, target = _parse_import_alias(raw_value)
            if alias and target:
                scoped.setdefault(alias, set()).add(target)
            continue

        imported = raw_value.lower()
        leaf = imported.split(".")[-1]
        scoped.setdefault(leaf, set()).add(imported)

    updates: List[Tuple[Optional[int], Optional[int], int, float, int]] = []
    for row in relation_rows:
        relation_id = int(row["id"])
        file_path = str(row["file_path"])
        src_qualname = str(row["src_qualname"]).strip()
        src_qualname_lower = src_qualname.lower()
        relation_kind = str(row["relation"]).strip().lower()
        dst_name = str(row["dst_name"]).strip()

        src_entity_id = entity_id_by_file_qualname.get((file_path, src_qualname_lower))
        if src_entity_id is None:
            src_entity_id = entity_id_by_qualname.get(src_qualname_lower)

        dst_entity_id, confidence = _resolve_relation_destination(
            relation_kind=relation_kind,
            file_path=file_path,
            src_qualname=src_qualname,
            dst_name=dst_name,
            src_entity_id=src_entity_id,
            entity_id_by_qualname=entity_id_by_qualname,
            entity_ids_by_suffix=entity_ids_by_suffix,
            entity_ids_by_name=entity_ids_by_name,
            entity_ids_by_module_and_name=entity_ids_by_module_and_name,
            entity_ids_by_class_and_name=entity_ids_by_class_and_name,
            entity_kind_by_id=entity_kind_by_id,
            entity_qualname_by_id=entity_qualname_by_id,
            imports_by_scope=imports_by_scope,
        )

        resolved = int(src_entity_id is not None and dst_entity_id is not None)
        if not resolved:
            confidence = 0.0
        updates.append(
            (
                src_entity_id,
                dst_entity_id,
                resolved,
                round(float(confidence), 4),
                relation_id,
            )
        )

    conn.executemany(
        """
        UPDATE relations
        SET src_entity_id = ?,
            dst_entity_id = ?,
            resolved = ?,
            confidence = ?
        WHERE id = ?
        """,
        updates,
    )


def _derive_rich_relations(conn: sqlite3.Connection) -> None:
    required_columns = {"src_entity_id", "dst_entity_id", "resolved", "confidence"}
    if not required_columns.issubset(_table_columns(conn, "relations")):
        return

    conn.execute("DELETE FROM relations WHERE relation IN ('instantiates', 'overrides')")

    conn.execute(
        """
        INSERT OR IGNORE INTO relations(
            file_path, src_qualname, dst_name, relation, line,
            src_entity_id, dst_entity_id, resolved, confidence
        )
        SELECT
            r.file_path,
            r.src_qualname,
            COALESCE(cls.qualname, r.dst_name),
            'instantiates',
            r.line,
            r.src_entity_id,
            r.dst_entity_id,
            1,
            r.confidence
        FROM relations r
        JOIN entities cls
            ON cls.id = r.dst_entity_id
        WHERE r.relation = 'calls'
          AND r.resolved = 1
          AND cls.kind = 'class'
        """
    )

    class_rows = conn.execute(
        """
        SELECT id, qualname
        FROM entities
        WHERE kind = 'class'
        """
    ).fetchall()
    if not class_rows:
        return

    class_id_by_qualname: Dict[str, int] = {
        str(row["qualname"]).strip().lower(): int(row["id"]) for row in class_rows
    }

    method_rows = conn.execute(
        """
        SELECT id, file_path, name, qualname, line
        FROM entities
        WHERE kind = 'method'
        """
    ).fetchall()

    methods_by_class_and_name: DefaultDict[Tuple[int, str], List[sqlite3.Row]] = defaultdict(list)
    for row in method_rows:
        qualname = str(row["qualname"]).strip()
        if "." not in qualname:
            continue
        class_qualname = qualname.rsplit(".", 1)[0].lower()
        class_id = class_id_by_qualname.get(class_qualname)
        if class_id is None:
            continue
        name = str(row["name"]).strip().lower()
        methods_by_class_and_name[(class_id, name)].append(row)

    inheritance_rows = conn.execute(
        """
        SELECT src_entity_id AS subclass_id, dst_entity_id AS base_class_id
        FROM relations
        WHERE relation = 'inherits'
          AND resolved = 1
          AND src_entity_id IS NOT NULL
          AND dst_entity_id IS NOT NULL
        """
    ).fetchall()

    override_rows: List[Tuple[str, str, str, int, int, int, float]] = []
    seen: Set[Tuple[int, int]] = set()

    for row in inheritance_rows:
        subclass_id = int(row["subclass_id"])
        base_class_id = int(row["base_class_id"])

        subclass_method_keys = {
            method_name for class_id, method_name in methods_by_class_and_name if class_id == subclass_id
        }
        if not subclass_method_keys:
            continue

        for method_name in subclass_method_keys:
            subclass_methods = methods_by_class_and_name.get((subclass_id, method_name), [])
            base_methods = methods_by_class_and_name.get((base_class_id, method_name), [])
            if not subclass_methods or not base_methods:
                continue

            for subclass_method in subclass_methods:
                subclass_method_id = int(subclass_method["id"])
                for base_method in base_methods:
                    base_method_id = int(base_method["id"])
                    pair_key = (subclass_method_id, base_method_id)
                    if pair_key in seen:
                        continue
                    seen.add(pair_key)
                    override_rows.append(
                        (
                            str(subclass_method["file_path"]),
                            str(subclass_method["qualname"]),
                            str(base_method["qualname"]),
                            int(subclass_method["line"]),
                            subclass_method_id,
                            base_method_id,
                            1.0,
                        )
                    )

    if override_rows:
        conn.executemany(
            """
            INSERT OR IGNORE INTO relations(
                file_path, src_qualname, dst_name, relation, line,
                src_entity_id, dst_entity_id, resolved, confidence
            )
            VALUES (?, ?, ?, 'overrides', ?, ?, ?, 1, ?)
            """,
            override_rows,
        )


def rebuild_entity_graph(
    files: Sequence[Path], codebase_root: Optional[Path] = None
) -> Tuple[int, int, int]:
    """Rebuild the entity graph from scratch for the provided file list."""
    root = codebase_root or Path.cwd()
    db_path = get_entities_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    indexed_files = 0
    indexed_entities = 0
    indexed_relations = 0

    with FileLock(db_path):
        with _connect() as conn:
            conn.execute("DELETE FROM relations")
            conn.execute("DELETE FROM entities")

            for file_path in files:
                if not file_path.exists():
                    continue
                try:
                    rel_path = str(file_path.relative_to(root))
                except ValueError:
                    rel_path = str(file_path)
                if not _EXTRACTOR_REGISTRY.supports_path(rel_path):
                    continue

                content = file_path.read_text(encoding="utf-8", errors="ignore")
                entity_count, relation_count = _index_file_content(conn, rel_path, content)
                if entity_count or relation_count:
                    indexed_files += 1
                indexed_entities += entity_count
                indexed_relations += relation_count

            _resolve_relations(conn)
            _derive_rich_relations(conn)
            conn.commit()

    return indexed_files, indexed_entities, indexed_relations


def update_entity_graph_incremental(
    changed_files: Sequence[str],
    deleted_files: Sequence[str],
    config: Dict[str, Any],
    codebase_root: Optional[Path] = None,
) -> Tuple[int, int, int]:
    """Incrementally update graph entries for changed/deleted files."""
    root = codebase_root or Path.cwd()
    db_path = get_entities_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    max_size = parse_size(config.get("max_file_size", "500KB"))
    touched_paths = list(dict.fromkeys([*changed_files, *deleted_files]))

    indexed_files = 0
    indexed_entities = 0
    indexed_relations = 0

    with FileLock(db_path):
        with _connect() as conn:
            for rel_path in touched_paths:
                _clear_file_graph(conn, rel_path)

            for rel_path in changed_files:
                file_path = root / rel_path
                if not file_path.exists() or not _EXTRACTOR_REGISTRY.supports_path(rel_path):
                    continue
                try:
                    if file_path.stat().st_size > max_size:
                        continue
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue

                entity_count, relation_count = _index_file_content(conn, rel_path, content)
                if entity_count or relation_count:
                    indexed_files += 1
                indexed_entities += entity_count
                indexed_relations += relation_count

            _resolve_relations(conn)
            _derive_rich_relations(conn)
            conn.commit()

    return indexed_files, indexed_entities, indexed_relations


def find_entities(
    symbol: str, kind: Optional[str] = None, limit: int = 10
) -> List[Dict[str, Any]]:
    """Find entities by symbol name or qualified name."""
    db_path = get_entities_db_path()
    if not db_path.exists():
        return []

    query = symbol.strip().lower()
    if not query:
        return []

    contains_pattern = f"%{query}%"
    prefix_pattern = f"{query}%"

    with _connect() as conn:
        sql = """
            SELECT file_path, name, qualname, kind, line
            FROM entities
            WHERE (
                lower(name) = ? OR
                lower(qualname) = ? OR
                lower(name) LIKE ? OR
                lower(qualname) LIKE ?
            )
        """
        params: List[Any] = [query, query, contains_pattern, contains_pattern]
        if kind:
            sql += " AND kind = ?"
            params.append(kind)
        sql += """
            ORDER BY
                CASE
                    WHEN lower(name) = ? THEN 0
                    WHEN lower(qualname) = ? THEN 1
                    WHEN lower(name) LIKE ? THEN 2
                    ELSE 3
                END,
                qualname ASC
            LIMIT ?
        """
        params.extend([query, query, prefix_pattern, int(limit)])
        rows = conn.execute(sql, params).fetchall()

    results: List[Dict[str, Any]] = []
    for row in rows:
        name = str(row["name"]).lower()
        qualname = str(row["qualname"]).lower()
        if name == query:
            score = 1.0
        elif qualname == query:
            score = 0.95
        elif name.startswith(query):
            score = 0.8
        else:
            score = 0.65
        results.append(
            {
                "file_path": row["file_path"],
                "name": row["name"],
                "qualname": row["qualname"],
                "kind": row["kind"],
                "line": row["line"],
                "score": score,
            }
        )
    return results


def search_entities(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Search entities (adapter for search command integration)."""
    return find_entities(query, limit=limit)


def find_callers(symbol: str, limit: int = 20, resolved_only: bool = False) -> List[Dict[str, Any]]:
    """Find callers for a symbol using call relationships."""
    db_path = get_entities_db_path()
    if not db_path.exists():
        return []

    query = symbol.strip().lower()
    if not query:
        return []

    exact = query
    suffix = f"%.{query}"
    contains = f"%{query}%"

    sql = """
        SELECT
            r.file_path,
            COALESCE(src.qualname, r.src_qualname) AS caller,
            COALESCE(dst.qualname, r.dst_name) AS callee,
            r.line,
            COALESCE(src.kind, 'unknown') AS caller_kind,
            r.resolved,
            r.confidence
        FROM relations r
        LEFT JOIN entities src
            ON src.id = r.src_entity_id
        LEFT JOIN entities dst
            ON dst.id = r.dst_entity_id
        WHERE r.relation = 'calls'
          AND (
                lower(r.dst_name) = ? OR
                lower(r.dst_name) LIKE ? OR
                lower(r.dst_name) LIKE ? OR
                lower(COALESCE(dst.name, '')) = ? OR
                lower(COALESCE(dst.qualname, '')) = ? OR
                lower(COALESCE(dst.qualname, '')) LIKE ? OR
                lower(COALESCE(dst.name, '')) LIKE ?
          )
    """
    params: List[Any] = [exact, suffix, contains, exact, exact, suffix, contains]
    if resolved_only:
        sql += " AND r.resolved = 1"
    sql += """
        ORDER BY r.resolved DESC, r.confidence DESC, r.file_path ASC, r.line ASC
        LIMIT ?
    """
    params.append(int(limit))

    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()

    return [
        {
            "file_path": row["file_path"],
            "caller": row["caller"],
            "callee": row["callee"],
            "line": row["line"],
            "caller_kind": row["caller_kind"],
            "resolved": bool(row["resolved"]),
            "confidence": float(row["confidence"]),
        }
        for row in rows
    ]


def find_callees(symbol: str, limit: int = 20, resolved_only: bool = False) -> List[Dict[str, Any]]:
    """Find callees for a caller symbol."""
    db_path = get_entities_db_path()
    if not db_path.exists():
        return []

    query = symbol.strip().lower()
    if not query:
        return []

    exact = query
    suffix = f"%.{query}"
    contains = f"%{query}%"

    sql = """
        SELECT
            r.file_path,
            COALESCE(src.qualname, r.src_qualname) AS caller,
            COALESCE(dst.qualname, r.dst_name) AS callee,
            r.line,
            COALESCE(dst.kind, 'unknown') AS callee_kind,
            r.resolved,
            r.confidence
        FROM relations r
        LEFT JOIN entities src
            ON src.id = r.src_entity_id
        LEFT JOIN entities dst
            ON dst.id = r.dst_entity_id
        WHERE r.relation = 'calls'
          AND (
                lower(r.src_qualname) = ? OR
                lower(r.src_qualname) LIKE ? OR
                lower(COALESCE(src.name, '')) = ? OR
                lower(COALESCE(src.qualname, '')) = ? OR
                lower(COALESCE(src.qualname, '')) LIKE ? OR
                lower(COALESCE(src.name, '')) LIKE ?
          )
    """
    params: List[Any] = [exact, suffix, exact, exact, suffix, contains]
    if resolved_only:
        sql += " AND r.resolved = 1"
    sql += """
        ORDER BY r.resolved DESC, r.confidence DESC, r.file_path ASC, r.line ASC
        LIMIT ?
    """
    params.append(int(limit))

    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()

    return [
        {
            "file_path": row["file_path"],
            "caller": row["caller"],
            "callee": row["callee"],
            "line": row["line"],
            "callee_kind": row["callee_kind"],
            "resolved": bool(row["resolved"]),
            "confidence": float(row["confidence"]),
        }
        for row in rows
    ]


def find_subclasses(symbol: str, limit: int = 20, resolved_only: bool = False) -> List[Dict[str, Any]]:
    """Find subclasses inheriting from a class symbol."""
    db_path = get_entities_db_path()
    if not db_path.exists():
        return []

    query = symbol.strip().lower()
    if not query:
        return []

    exact = query
    suffix = f"%.{query}"
    contains = f"%{query}%"

    sql = """
        SELECT
            r.file_path,
            COALESCE(src.qualname, r.src_qualname) AS subclass,
            COALESCE(dst.qualname, r.dst_name) AS base_class,
            r.line,
            r.resolved,
            r.confidence
        FROM relations r
        LEFT JOIN entities src
            ON src.id = r.src_entity_id
        LEFT JOIN entities dst
            ON dst.id = r.dst_entity_id
        WHERE r.relation = 'inherits'
          AND (
                lower(r.dst_name) = ? OR
                lower(r.dst_name) LIKE ? OR
                lower(r.dst_name) LIKE ? OR
                lower(COALESCE(dst.name, '')) = ? OR
                lower(COALESCE(dst.qualname, '')) = ? OR
                lower(COALESCE(dst.qualname, '')) LIKE ? OR
                lower(COALESCE(dst.name, '')) LIKE ?
          )
    """
    params: List[Any] = [exact, suffix, contains, exact, exact, suffix, contains]
    if resolved_only:
        sql += " AND r.resolved = 1"
    sql += """
        ORDER BY r.resolved DESC, r.confidence DESC, r.file_path ASC, r.line ASC
        LIMIT ?
    """
    params.append(int(limit))

    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()

    return [
        {
            "file_path": row["file_path"],
            "subclass": row["subclass"],
            "base_class": row["base_class"],
            "line": row["line"],
            "resolved": bool(row["resolved"]),
            "confidence": float(row["confidence"]),
        }
        for row in rows
    ]
