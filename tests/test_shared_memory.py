"""Tests for twin_mind.shared_memory module (semantic decisions index)."""

from contextlib import nullcontext
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


def _write_jsonl(path: Path, entries: list) -> None:
    """Helper: write a list of dicts to a JSONL file."""
    with open(path, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


SAMPLE_ENTRIES = [
    {"ts": "2024-01-01T10:00:00", "msg": "Use JWT for authentication", "tag": "arch", "author": "alice"},
    {"ts": "2024-01-02T11:00:00", "msg": "Prefer postgres over mysql", "tag": "db", "author": "bob"},
]


class TestBuildDecisionsIndex:
    """Tests for build_decisions_index."""

    def test_build_creates_mv2(self, tmp_path: Any) -> None:
        """build_decisions_index() creates decisions.mv2 from JSONL."""
        brain_dir = tmp_path / ".claude"
        brain_dir.mkdir()
        jsonl_path = brain_dir / "decisions.jsonl"
        mv2_path = brain_dir / "decisions.mv2"
        _write_jsonl(jsonl_path, SAMPLE_ENTRIES)

        mock_sdk = MagicMock()
        mock_mem = MagicMock()
        mock_sdk.use.return_value.__enter__ = MagicMock(return_value=mock_mem)
        mock_sdk.use.return_value.__exit__ = MagicMock(return_value=False)

        with (
            patch("twin_mind.shared_memory.get_decisions_path", return_value=jsonl_path),
            patch("twin_mind.shared_memory.get_decisions_mv2_path", return_value=mv2_path),
            patch("twin_mind.shared_memory.get_memvid_sdk", return_value=mock_sdk),
        ):
            from twin_mind.shared_memory import build_decisions_index

            result = build_decisions_index()

        assert result is True
        mock_sdk.use.assert_called_once_with("basic", str(mv2_path), mode="create")
        assert mock_mem.put.call_count == len(SAMPLE_ENTRIES)

    def test_build_returns_false_when_no_entries(self, tmp_path: Any) -> None:
        """build_decisions_index() returns False when JSONL is empty."""
        brain_dir = tmp_path / ".claude"
        brain_dir.mkdir()
        jsonl_path = brain_dir / "decisions.jsonl"
        mv2_path = brain_dir / "decisions.mv2"
        # Empty file
        jsonl_path.write_text("")

        with (
            patch("twin_mind.shared_memory.get_decisions_path", return_value=jsonl_path),
            patch("twin_mind.shared_memory.get_decisions_mv2_path", return_value=mv2_path),
        ):
            from twin_mind.shared_memory import build_decisions_index

            result = build_decisions_index()

        assert result is False


class TestSearchSharedMemories:
    """Tests for search_shared_memories routing logic."""

    def test_uses_semantic_when_mv2_exists(self, tmp_path: Any) -> None:
        """search_shared_memories uses MV2 when it exists."""
        brain_dir = tmp_path / ".claude"
        brain_dir.mkdir()
        jsonl_path = brain_dir / "decisions.jsonl"
        mv2_path = brain_dir / "decisions.mv2"
        _write_jsonl(jsonl_path, SAMPLE_ENTRIES)
        mv2_path.touch()  # Exists

        mock_sdk = MagicMock()
        mock_mem = MagicMock()
        mock_mem.find.return_value = {
            "hits": [
                {
                    "text": "Use JWT for authentication",
                    "score": 0.95,
                    "tags": ["category:arch", "author:alice"],
                    "uri": "twin-mind://shared/2024-01-01T10:00:00",
                }
            ]
        }
        mock_sdk.use.return_value.__enter__ = MagicMock(return_value=mock_mem)
        mock_sdk.use.return_value.__exit__ = MagicMock(return_value=False)

        with (
            patch("twin_mind.shared_memory.get_decisions_path", return_value=jsonl_path),
            patch("twin_mind.shared_memory.get_decisions_mv2_path", return_value=mv2_path),
            patch("twin_mind.shared_memory.get_memvid_sdk", return_value=mock_sdk),
        ):
            from twin_mind.shared_memory import search_shared_memories

            results = search_shared_memories("JWT auth", top_k=5)

        assert len(results) == 1
        score, entry = results[0]
        assert entry["msg"] == "Use JWT for authentication"
        assert entry["tag"] == "arch"
        mock_mem.find.assert_called_once()

    def test_falls_back_to_text_when_no_mv2(self, tmp_path: Any) -> None:
        """search_shared_memories falls back to text search when MV2 absent and build fails."""
        brain_dir = tmp_path / ".claude"
        brain_dir.mkdir()
        jsonl_path = brain_dir / "decisions.jsonl"
        mv2_path = brain_dir / "decisions.mv2"  # Does NOT exist
        _write_jsonl(jsonl_path, SAMPLE_ENTRIES)

        with (
            patch("twin_mind.shared_memory.get_decisions_path", return_value=jsonl_path),
            patch("twin_mind.shared_memory.get_decisions_mv2_path", return_value=mv2_path),
            # build_decisions_index fails → should fall back to text
            patch("twin_mind.shared_memory.build_decisions_index", return_value=False),
        ):
            from twin_mind.shared_memory import search_shared_memories

            results = search_shared_memories("JWT auth", top_k=5)

        assert len(results) >= 1
        scores = [r[0] for r in results]
        assert all(isinstance(s, int) for s in scores)

    def test_write_shared_memory_updates_mv2_incrementally(self, tmp_path: Any) -> None:
        """write_shared_memory updates MV2 if it already exists."""
        brain_dir = tmp_path / ".claude"
        brain_dir.mkdir()
        jsonl_path = brain_dir / "decisions.jsonl"
        mv2_path = brain_dir / "decisions.mv2"
        mv2_path.touch()  # MV2 exists

        mock_sdk = MagicMock()
        mock_mem = MagicMock()
        mock_sdk.use.return_value.__enter__ = MagicMock(return_value=mock_mem)
        mock_sdk.use.return_value.__exit__ = MagicMock(return_value=False)

        with (
            patch("twin_mind.shared_memory.get_decisions_path", return_value=jsonl_path),
            patch("twin_mind.shared_memory.get_decisions_mv2_path", return_value=mv2_path),
            patch("twin_mind.shared_memory.get_memvid_sdk", return_value=mock_sdk),
            patch("twin_mind.shared_memory.get_git_author", return_value="tester"),
        ):
            from twin_mind.shared_memory import write_shared_memory

            result = write_shared_memory("New decision about caching", tag="perf")

        assert result is True
        # MV2 was opened in "open" mode for incremental update
        mock_sdk.use.assert_called_once_with("basic", str(mv2_path), mode="open")
        mock_mem.put.assert_called_once()
        # JSONL was written
        assert jsonl_path.exists()
        lines = [json.loads(l) for l in jsonl_path.read_text().strip().splitlines()]
        assert lines[0]["msg"] == "New decision about caching"
        assert lines[0]["tag"] == "perf"

    def test_write_shared_memory_skips_mv2_when_absent(self, tmp_path: Any) -> None:
        """write_shared_memory does not attempt MV2 update when MV2 does not exist."""
        brain_dir = tmp_path / ".claude"
        brain_dir.mkdir()
        jsonl_path = brain_dir / "decisions.jsonl"
        mv2_path = brain_dir / "decisions.mv2"  # Does NOT exist

        mock_sdk = MagicMock()

        with (
            patch("twin_mind.shared_memory.get_decisions_path", return_value=jsonl_path),
            patch("twin_mind.shared_memory.get_decisions_mv2_path", return_value=mv2_path),
            patch("twin_mind.shared_memory.get_memvid_sdk", return_value=mock_sdk),
            patch("twin_mind.shared_memory.get_git_author", return_value="tester"),
        ):
            from twin_mind.shared_memory import write_shared_memory

            result = write_shared_memory("Decision without MV2", tag="arch")

        assert result is True
        mock_sdk.use.assert_not_called()

    def test_write_shared_memory_uses_file_locks(self, tmp_path: Any) -> None:
        """Shared writes lock both JSONL and MV2 when MV2 exists."""
        brain_dir = tmp_path / ".claude"
        brain_dir.mkdir()
        jsonl_path = brain_dir / "decisions.jsonl"
        mv2_path = brain_dir / "decisions.mv2"
        mv2_path.touch()

        mock_sdk = MagicMock()
        mock_mem = MagicMock()
        mock_sdk.use.return_value.__enter__ = MagicMock(return_value=mock_mem)
        mock_sdk.use.return_value.__exit__ = MagicMock(return_value=False)

        with (
            patch("twin_mind.shared_memory.get_decisions_path", return_value=jsonl_path),
            patch("twin_mind.shared_memory.get_decisions_mv2_path", return_value=mv2_path),
            patch("twin_mind.shared_memory.get_memvid_sdk", return_value=mock_sdk),
            patch("twin_mind.shared_memory.get_git_author", return_value="tester"),
            patch(
                "twin_mind.shared_memory.FileLock",
                side_effect=lambda *args, **kwargs: nullcontext(),
            ) as mock_lock,
        ):
            from twin_mind.shared_memory import write_shared_memory

            result = write_shared_memory("Locked write", tag="arch")

        assert result is True
        assert mock_lock.call_count == 2  # decisions.jsonl + decisions.mv2
