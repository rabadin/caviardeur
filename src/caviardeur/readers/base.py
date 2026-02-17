from dataclasses import dataclass, field
from typing import Any


@dataclass
class TextChunk:
    """A piece of text extracted from a document, with its location metadata."""

    text: str
    # Offset of this chunk's first character within the concatenated raw_text
    offset: int = 0
    # Format-specific location metadata
    location: dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentContent:
    """Full text content extracted from a document."""

    chunks: list[TextChunk]
    # Opaque metadata needed by the writer to reconstruct the document
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def raw_text(self) -> str:
        """Concatenate all chunks into a single string for NER processing."""
        return "".join(chunk.text for chunk in self.chunks)

    def assign_offsets(self) -> None:
        """Compute and assign character offsets for each chunk."""
        offset = 0
        for chunk in self.chunks:
            chunk.offset = offset
            offset += len(chunk.text)
