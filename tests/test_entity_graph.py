"""Tests for twin_mind.entity_graph module."""

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

        callees = find_callees("login")
        assert any("authenticate" in item["callee"] for item in callees)

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
