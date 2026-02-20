"""Entity extraction and knowledge graph queries for twin-mind."""

import ast
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any, DefaultDict, Dict, List, Optional, Sequence, Set, Tuple

from twin_mind.config import parse_size
from twin_mind.fs import FileLock, get_entities_db_path


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

            _resolve_relations(conn)
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

            _resolve_relations(conn)
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
