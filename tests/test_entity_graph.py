"""Tests for twin_mind.entity_graph module."""

import sqlite3
from pathlib import Path
from typing import Any, Dict

from twin_mind.entity_graph import (
    extract_python_entities,
    find_callees,
    find_callers,
    find_entities,
    rebuild_entity_graph,
    update_entity_graph_incremental,
)


class TestExtractPythonEntities:
    """Tests for Python AST extraction."""

    def test_extracts_entities_and_relations(self) -> None:
        source = """
import utils

class Base:
    pass

class Service(Base):
    def authenticate(self, token):
        return helper(token)

def helper(token):
    return token
"""
        entities, relations = extract_python_entities("src/auth.py", source)

        qualnames = {entity["qualname"] for entity in entities}
        assert "src.auth.Service" in qualnames
        assert "src.auth.Service.authenticate" in qualnames
        assert "src.auth.helper" in qualnames

        rel_kinds = {(rel["relation"], rel["src_qualname"], rel["dst_name"]) for rel in relations}
        assert ("inherits", "src.auth.Service", "Base") in rel_kinds
        assert ("calls", "src.auth.Service.authenticate", "helper") in rel_kinds
        assert ("imports", "src.auth", "utils") in rel_kinds

    def test_extracts_import_alias_and_relative_imports(self) -> None:
        source = """
import pkg.helpers as helpers_mod
from .auth import authenticate as auth_fn
"""
        _, relations = extract_python_entities("pkg/api.py", source)

        rel_kinds = {(rel["relation"], rel["src_qualname"], rel["dst_name"]) for rel in relations}
        assert ("imports", "pkg.api", "pkg.helpers") in rel_kinds
        assert ("imports_alias", "pkg.api", "helpers_mod=pkg.helpers") in rel_kinds
        assert ("imports", "pkg.api", "pkg.auth.authenticate") in rel_kinds
        assert ("imports_alias", "pkg.api", "auth_fn=pkg.auth.authenticate") in rel_kinds


class TestEntityGraphLifecycle:
    """Tests for graph build and query flows."""

    def test_rebuild_and_query_call_graph(
        self, temp_dir: Path, sample_config: Dict[str, Any]
    ) -> None:
        service = temp_dir / "service.py"
        service.write_text(
            """
def authenticate(token):
    return token
"""
        )
        api = temp_dir / "api.py"
        api.write_text(
            """
from service import authenticate

def login(token):
    return authenticate(token)
"""
        )

        indexed_files, entity_count, relation_count = rebuild_entity_graph(
            [service, api], codebase_root=temp_dir
        )

        assert indexed_files == 2
        assert entity_count > 0
        assert relation_count > 0

        matches = find_entities("authenticate")
        assert any(item["qualname"].endswith(".authenticate") for item in matches)

        callers = find_callers("authenticate")
        assert any(item["caller"].endswith(".login") for item in callers)
        assert any(item["resolved"] for item in callers)

        resolved_callers = find_callers("authenticate", resolved_only=True)
        assert any(item["callee"].endswith(".authenticate") for item in resolved_callers)

        callees = find_callees("login")
        assert any("authenticate" in item["callee"] for item in callees)
        assert any(item["resolved"] for item in callees)

        # sample_config is intentionally passed to exercise the public incremental API shape.
        assert sample_config["max_file_size"] == "500KB"

    def test_incremental_update_replaces_old_symbols(
        self, temp_dir: Path, sample_config: Dict[str, Any]
    ) -> None:
        service = temp_dir / "service.py"
        service.write_text(
            """
def foo(token):
    return token
"""
        )
        api = temp_dir / "api.py"
        api.write_text(
            """
from service import foo

def login(token):
    return foo(token)
"""
        )

        rebuild_entity_graph([service, api], codebase_root=temp_dir)
        assert find_entities("foo")

        service.write_text(
            """
def bar(token):
    return token
"""
        )
        api.write_text(
            """
from service import bar

def login(token):
    return bar(token)
"""
        )

        update_entity_graph_incremental(
            changed_files=["service.py", "api.py"],
            deleted_files=[],
            config=sample_config,
            codebase_root=temp_dir,
        )

        assert find_entities("foo") == []
        assert find_entities("bar")
        assert find_callers("bar")
        assert find_callers("bar", resolved_only=True)

    def test_resolved_only_filters_unresolved_calls(
        self, temp_dir: Path, sample_config: Dict[str, Any]
    ) -> None:
        api = temp_dir / "api.py"
        api.write_text(
            """
def login(token):
    return external.authenticate(token)
"""
        )

        rebuild_entity_graph([api], codebase_root=temp_dir)

        callers = find_callers("external.authenticate")
        assert callers
        assert all(not item["resolved"] for item in callers)
        assert find_callers("external.authenticate", resolved_only=True) == []

        # sample_config is intentionally passed to exercise the public incremental API shape.
        assert sample_config["entities"]["enabled"] is True

    def test_resolves_alias_and_relative_import_calls(
        self, temp_dir: Path, sample_config: Dict[str, Any]
    ) -> None:
        package_dir = temp_dir / "pkg"
        sub_dir = package_dir / "sub"
        sub_dir.mkdir(parents=True, exist_ok=True)

        helpers = package_dir / "helpers.py"
        helpers.write_text(
            """
def authenticate(token):
    return token
"""
        )
        api = sub_dir / "api.py"
        api.write_text(
            """
import pkg.helpers as helpers_mod
from ..helpers import authenticate as auth_fn

def login(token):
    auth_fn(token)
    return helpers_mod.authenticate(token)
"""
        )

        rebuild_entity_graph([helpers, api], codebase_root=temp_dir)

        callers = find_callers("authenticate", resolved_only=True)
        login_callers = [item for item in callers if item["caller"].endswith(".login")]
        assert len(login_callers) == 2
        assert all(item["callee"].endswith("pkg.helpers.authenticate") for item in login_callers)
        assert all(item["resolved"] for item in login_callers)

        # sample_config is intentionally passed to exercise the public incremental API shape.
        assert sample_config["max_file_size"] == "500KB"

    def test_migrates_old_relations_schema_to_linked_edges(
        self, temp_dir: Path, sample_config: Dict[str, Any]
    ) -> None:
        db_path = temp_dir / ".claude" / "entities.sqlite"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db_path) as conn:
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
            conn.commit()

        service = temp_dir / "service.py"
        service.write_text(
            """
def authenticate(token):
    return token
"""
        )
        api = temp_dir / "api.py"
        api.write_text(
            """
from service import authenticate

def login(token):
    return authenticate(token)
"""
        )

        rebuild_entity_graph([service, api], codebase_root=temp_dir)

        with sqlite3.connect(db_path) as conn:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(relations)").fetchall()}
            assert {"src_entity_id", "dst_entity_id", "resolved", "confidence"} <= columns

            row = conn.execute(
                """
                SELECT src_entity_id, dst_entity_id, resolved, confidence
                FROM relations
                WHERE relation = 'calls'
                LIMIT 1
                """
            ).fetchone()
            assert row is not None
            assert row[0] is not None
            assert row[1] is not None
            assert row[2] == 1
            assert row[3] > 0

        # sample_config is intentionally passed to exercise the public incremental API shape.
        assert sample_config["max_file_size"] == "500KB"
