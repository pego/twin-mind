"""Entity extraction and knowledge graph queries for twin-mind."""

import ast
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from twin_mind.config import parse_size
from twin_mind.fs import FileLock, get_entities_db_path


class _PythonEntityVisitor(ast.NodeVisitor):
    """Extract entities and relationships from Python AST."""

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self.module_name = _module_name_from_path(file_path)
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
                self._add_relation(src, imported, "imports", getattr(node, "lineno", 0))
        self.generic_visit(node)
        return None

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
        src = self._current_scope()
        module = (node.module or "").strip()
        for alias in node.names:
            leaf = alias.name.strip()
            if not leaf:
                continue
            imported = f"{module}.{leaf}" if module else leaf
            self._add_relation(src, imported, "imports", getattr(node, "lineno", 0))
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
            line INTEGER NOT NULL DEFAULT 0
        )
        """
    )
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


def _index_file_content(
    conn: sqlite3.Connection, file_path: str, content: str
) -> Tuple[int, int]:
    entities, relations = extract_python_entities(file_path, content)
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
                if file_path.suffix.lower() != ".py" or not file_path.exists():
                    continue
                try:
                    rel_path = str(file_path.relative_to(root))
                except ValueError:
                    rel_path = str(file_path)

                content = file_path.read_text(encoding="utf-8", errors="ignore")
                entity_count, relation_count = _index_file_content(conn, rel_path, content)
                if entity_count or relation_count:
                    indexed_files += 1
                indexed_entities += entity_count
                indexed_relations += relation_count

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
                if not file_path.exists() or file_path.suffix.lower() != ".py":
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


def find_callers(symbol: str, limit: int = 20) -> List[Dict[str, Any]]:
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

    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT
                r.file_path,
                r.src_qualname AS caller,
                r.dst_name AS callee,
                r.line,
                COALESCE(e.kind, 'unknown') AS caller_kind
            FROM relations r
            LEFT JOIN entities e
                ON e.file_path = r.file_path
               AND e.qualname = r.src_qualname
            WHERE r.relation = 'calls'
              AND (
                    lower(r.dst_name) = ? OR
                    lower(r.dst_name) LIKE ? OR
                    lower(r.dst_name) LIKE ?
              )
            ORDER BY r.file_path ASC, r.line ASC
            LIMIT ?
            """,
            (exact, suffix, contains, int(limit)),
        ).fetchall()

    return [
        {
            "file_path": row["file_path"],
            "caller": row["caller"],
            "callee": row["callee"],
            "line": row["line"],
            "caller_kind": row["caller_kind"],
        }
        for row in rows
    ]


def find_callees(symbol: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Find callees for a caller symbol."""
    db_path = get_entities_db_path()
    if not db_path.exists():
        return []

    query = symbol.strip().lower()
    if not query:
        return []

    exact = query
    suffix = f"%.{query}"

    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT
                file_path,
                src_qualname AS caller,
                dst_name AS callee,
                line
            FROM relations
            WHERE relation = 'calls'
              AND (
                    lower(src_qualname) = ? OR
                    lower(src_qualname) LIKE ?
              )
            ORDER BY file_path ASC, line ASC
            LIMIT ?
            """,
            (exact, suffix, int(limit)),
        ).fetchall()

    return [
        {
            "file_path": row["file_path"],
            "caller": row["caller"],
            "callee": row["callee"],
            "line": row["line"],
        }
        for row in rows
    ]


def find_subclasses(symbol: str, limit: int = 20) -> List[Dict[str, Any]]:
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

    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT file_path, src_qualname AS subclass, dst_name AS base_class, line
            FROM relations
            WHERE relation = 'inherits'
              AND (
                    lower(dst_name) = ? OR
                    lower(dst_name) LIKE ? OR
                    lower(dst_name) LIKE ?
              )
            ORDER BY file_path ASC, line ASC
            LIMIT ?
            """,
            (exact, suffix, contains, int(limit)),
        ).fetchall()

    return [
        {
            "file_path": row["file_path"],
            "subclass": row["subclass"],
            "base_class": row["base_class"],
            "line": row["line"],
        }
        for row in rows
    ]
