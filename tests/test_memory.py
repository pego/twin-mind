"""Tests for twin_mind.memory module."""

import pytest

from twin_mind.memory import parse_timeline_entry


class TestParseTimelineEntry:
    """Tests for parse_timeline_entry function."""

    def test_parse_basic_entry(self) -> None:
        """Test parsing a basic timeline entry."""
        entry = {
            "preview": "This is a test memory",
            "uri": "twin-mind://memory/20240101_120000",
            "timestamp": 1704110400,
            "frame_id": "abc123",
        }

        result = parse_timeline_entry(entry)

        assert result["text"] == "This is a test memory"
        assert result["uri"] == "twin-mind://memory/20240101_120000"
        assert result["timestamp"] == 1704110400
        assert result["frame_id"] == "abc123"
        assert result["title"] == "untitled"
        assert result["tags"] == []

    def test_parse_entry_with_title(self) -> None:
        """Test parsing an entry with embedded title."""
        entry = {
            "preview": "Memory content\ntitle: My Title\nuri: custom://uri",
            "uri": "",
            "timestamp": 0,
        }

        result = parse_timeline_entry(entry)

        assert result["title"] == "My Title"
        assert result["text"] == "Memory content"
        assert result["uri"] == "custom://uri"

    def test_parse_entry_with_tags(self) -> None:
        """Test parsing an entry with embedded tags."""
        entry = {
            "preview": "Memory content\ntags: arch,design,feature",
            "uri": "",
            "timestamp": 0,
        }

        result = parse_timeline_entry(entry)

        assert result["tags"] == ["arch", "design", "feature"]

    def test_parse_entry_with_all_metadata(self) -> None:
        """Test parsing an entry with all embedded metadata."""
        entry = {
            "preview": "This is the main text\ntitle: Important Decision\nuri: twin-mind://custom\ntags: arch,important",
            "uri": "twin-mind://memory/123",
            "timestamp": 1704110400,
            "frame_id": "frame1",
        }

        result = parse_timeline_entry(entry)

        assert result["title"] == "Important Decision"
        assert result["text"] == "This is the main text"
        # Original URI should be used since preview URI is parsed second
        assert result["uri"] == "twin-mind://memory/123"
        assert result["tags"] == ["arch", "important"]

    def test_parse_empty_entry(self) -> None:
        """Test parsing an empty entry."""
        entry = {}

        result = parse_timeline_entry(entry)

        assert result["title"] == "untitled"
        assert result["text"] == ""
        assert result["uri"] == ""
        assert result["tags"] == []
        assert result["timestamp"] == 0
        assert result["frame_id"] == ""

    def test_parse_entry_with_empty_tags(self) -> None:
        """Test parsing an entry with empty tags line."""
        entry = {
            "preview": "Content\ntags: ",
            "uri": "",
            "timestamp": 0,
        }

        result = parse_timeline_entry(entry)

        assert result["tags"] == []

    def test_parse_entry_with_multiline_text(self) -> None:
        """Test parsing an entry with multiline text content."""
        entry = {
            "preview": "Line 1\nLine 2\nLine 3\ntitle: Test\ntags: test",
            "uri": "",
            "timestamp": 0,
        }

        result = parse_timeline_entry(entry)

        assert result["text"] == "Line 1\nLine 2\nLine 3"
        assert result["title"] == "Test"
        assert result["tags"] == ["test"]

    def test_parse_entry_preserves_uri_from_entry(self) -> None:
        """Test that URI from entry is preferred over preview."""
        entry = {
            "preview": "Content",
            "uri": "twin-mind://primary",
            "timestamp": 0,
        }

        result = parse_timeline_entry(entry)

        assert result["uri"] == "twin-mind://primary"

    def test_parse_entry_uses_preview_uri_if_entry_empty(self) -> None:
        """Test that preview URI is used if entry URI is empty."""
        entry = {
            "preview": "Content\nuri: twin-mind://fallback",
            "uri": "",
            "timestamp": 0,
        }

        result = parse_timeline_entry(entry)

        assert result["uri"] == "twin-mind://fallback"

    def test_parse_entry_with_whitespace_in_tags(self) -> None:
        """Test parsing tags with whitespace."""
        entry = {
            "preview": "Content\ntags:  tag1 , tag2 , tag3 ",
            "uri": "",
            "timestamp": 0,
        }

        result = parse_timeline_entry(entry)

        assert result["tags"] == ["tag1", "tag2", "tag3"]
