"""Tests for twin_mind.entity_graph module."""

import sqlite3
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

from twin_mind.entity_graph import (
    extract_entities,
    extract_python_entities,
    find_callees,
    find_callers,
    find_entities,
    rebuild_entity_graph,
    supported_entity_languages,
    update_entity_graph_incremental,
)


class TestExtractPythonEntities:
    """Tests for Python AST extraction."""

    @patch("twin_mind.entity_graph.extract_javascript_entities_with_oxc")
    def test_javascript_extractor_uses_oxc_when_available(self, mock_oxc: Any) -> None:
        mock_oxc.return_value = (
            [
                {
                    "file_path": "src/app.js",
                    "name": "src.app",
                    "qualname": "src.app",
                    "kind": "module",
                    "line": 1,
                }
            ],
            [],
        )

        entities, relations = extract_entities("src/app.js", "function login() {}")
        assert entities
        assert relations == []
        mock_oxc.assert_called_once()

    def test_extractor_registry_dispatches_by_extension(self) -> None:
        entities, relations = extract_entities("src/app.go", "package main\n")
        assert entities == []
        assert relations == []

        js_entities, _ = extract_entities("src/app.js", "function login() { return true; }")
        assert any(entity["qualname"].endswith(".login") for entity in js_entities)

        py_entities, _ = extract_entities("src/app.py", "def login():\n    return True\n")
        assert any(entity["qualname"].endswith(".login") for entity in py_entities)
        assert "python" in supported_entity_languages()
        assert "javascript" in supported_entity_languages()
        assert "typescript" in supported_entity_languages()

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

    def test_extracts_javascript_entities_and_relations(self) -> None:
        source = """
import { authenticate as authFn } from "./service.js";
import * as serviceNs from "./service.js";

class ApiClient extends BaseClient {
  login(token) {
    authFn(token);
    return serviceNs.authenticate(token);
  }
}

export function bootstrap(token) {
  return new ApiClient();
}
"""
        entities, relations = extract_entities("src/api.js", source)

        qualnames = {entity["qualname"] for entity in entities}
        assert "src.api.ApiClient" in qualnames
        assert "src.api.ApiClient.login" in qualnames
        assert "src.api.bootstrap" in qualnames

        rel_kinds = {(rel["relation"], rel["src_qualname"], rel["dst_name"]) for rel in relations}
        assert ("inherits", "src.api.ApiClient", "BaseClient") in rel_kinds
        assert ("imports", "src.api", "src.service.authenticate") in rel_kinds
        assert ("imports_alias", "src.api", "authFn=src.service.authenticate") in rel_kinds
        assert ("imports_alias", "src.api", "serviceNs=src.service") in rel_kinds
        assert ("calls", "src.api.ApiClient.login", "authFn") in rel_kinds
        assert ("calls", "src.api.ApiClient.login", "serviceNs.authenticate") in rel_kinds
        assert ("calls", "src.api.bootstrap", "ApiClient") in rel_kinds


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

    def test_rebuild_and_query_typescript_call_graph(
        self, temp_dir: Path, sample_config: Dict[str, Any]
    ) -> None:
        service = temp_dir / "service.ts"
        service.write_text(
            """
export function authenticate(token: string) {
    return token;
}
"""
        )
        api = temp_dir / "api.ts"
        api.write_text(
            """
import { authenticate as authFn } from "./service";
import * as serviceNs from "./service";

export function login(token: string) {
    return authFn(token);
}

export function loginViaNs(token: string) {
    return serviceNs.authenticate(token);
}
"""
        )

        indexed_files, entity_count, relation_count = rebuild_entity_graph(
            [service, api], codebase_root=temp_dir
        )

        assert indexed_files == 2
        assert entity_count > 0
        assert relation_count > 0

        callers = find_callers("authenticate", resolved_only=True)
        assert any(item["caller"].endswith(".login") for item in callers)
        assert any(item["caller"].endswith(".loginViaNs") for item in callers)
        assert all(item["callee"].endswith("service.authenticate") for item in callers)

        callees = find_callees("loginViaNs", resolved_only=True)
        assert any(item["callee"].endswith("service.authenticate") for item in callees)

        # sample_config is intentionally passed to exercise the public incremental API shape.
        assert sample_config["entities"]["enabled"] is True

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

    def test_derives_instantiates_and_overrides_relations(
        self, temp_dir: Path, sample_config: Dict[str, Any]
    ) -> None:
        models = temp_dir / "models.py"
        models.write_text(
            """
class BaseService:
    def run(self):
        return "base"

class Service(BaseService):
    def run(self):
        return "service"

def build_service():
    return Service()
"""
        )

        rebuild_entity_graph([models], codebase_root=temp_dir)

        db_path = temp_dir / ".claude" / "entities.sqlite"
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            instantiates = conn.execute(
                """
                SELECT src_qualname, dst_name, resolved
                FROM relations
                WHERE relation = 'instantiates'
                """
            ).fetchall()
            assert any(
                row["src_qualname"].endswith(".build_service")
                and row["dst_name"].endswith(".Service")
                and int(row["resolved"]) == 1
                for row in instantiates
            )

            overrides = conn.execute(
                """
                SELECT src_qualname, dst_name, resolved
                FROM relations
                WHERE relation = 'overrides'
                """
            ).fetchall()
            assert any(
                row["src_qualname"].endswith(".Service.run")
                and row["dst_name"].endswith(".BaseService.run")
                and int(row["resolved"]) == 1
                for row in overrides
            )

        # sample_config is intentionally passed to exercise the public incremental API shape.
        assert sample_config["entities"]["enabled"] is True
