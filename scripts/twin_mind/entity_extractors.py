"""Language-specific entity extraction registry for the knowledge graph."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

EntityRows = List[Dict[str, Any]]
RelationRows = List[Dict[str, Any]]
EntityExtractionResult = Tuple[EntityRows, RelationRows]
EntityExtractorFn = Callable[[str, str], EntityExtractionResult]


@dataclass(frozen=True)
class EntityExtractor:
    """Entity extractor definition for one language."""

    language: str
    extensions: Tuple[str, ...]
    extract: EntityExtractorFn

    def supports(self, file_path: str) -> bool:
        ext = Path(file_path).suffix.lower()
        return ext in self.extensions


class EntityExtractorRegistry:
    """Registry of supported entity extractors by file extension."""

    def __init__(self) -> None:
        self._by_extension: Dict[str, EntityExtractor] = {}

    def register(self, extractor: EntityExtractor) -> None:
        for ext in extractor.extensions:
            self._by_extension[ext.lower()] = extractor

    def get_extractor_for_path(self, file_path: str) -> Optional[EntityExtractor]:
        ext = Path(file_path).suffix.lower()
        return self._by_extension.get(ext)

    def supports_path(self, file_path: str) -> bool:
        return self.get_extractor_for_path(file_path) is not None

    def extract_for_path(self, file_path: str, content: str) -> EntityExtractionResult:
        extractor = self.get_extractor_for_path(file_path)
        if extractor is None:
            return [], []
        return extractor.extract(file_path, content)

    def supported_languages(self) -> List[str]:
        seen = set()
        languages: List[str] = []
        for extractor in self._by_extension.values():
            if extractor.language in seen:
                continue
            seen.add(extractor.language)
            languages.append(extractor.language)
        return sorted(languages)

    def supported_extensions(self) -> List[str]:
        return sorted(self._by_extension.keys())
