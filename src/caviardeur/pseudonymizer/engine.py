from ..detectors.base import DetectedEntity
from ..readers.base import DocumentContent, TextChunk
from .mapping import MappingStore


def _find_chunk_for_offset(chunks: list[TextChunk], global_start: int, global_end: int) -> list[tuple[int, int, int]]:
    """Map a global offset range to specific chunks and their local offsets.

    Returns a list of (chunk_index, local_start, local_end) tuples.
    An entity may span multiple chunks.
    """
    result = []
    for i, chunk in enumerate(chunks):
        chunk_start = chunk.offset
        chunk_end = chunk.offset + len(chunk.text)

        # Check for overlap between entity span and chunk span
        overlap_start = max(global_start, chunk_start)
        overlap_end = min(global_end, chunk_end)

        if overlap_start < overlap_end:
            local_start = overlap_start - chunk_start
            local_end = overlap_end - chunk_start
            result.append((i, local_start, local_end))

    return result


def pseudonymize(
    content: DocumentContent,
    entities: list[DetectedEntity],
    mapping: MappingStore,
) -> DocumentContent:
    """Replace detected entities in the document content with pseudonyms.

    Returns a new DocumentContent with modified chunk texts.
    """
    if not entities:
        return content

    # Sort entities by start position descending so we can replace from the end
    # without invalidating earlier offsets
    sorted_entities = sorted(entities, key=lambda e: e.start, reverse=True)

    # Build a mutable copy of chunk texts
    chunk_texts: dict[int, str] = {}
    for i, chunk in enumerate(content.chunks):
        chunk_texts[i] = chunk.text

    for entity in sorted_entities:
        pseudonym = mapping.get_or_create(entity.text, entity.entity_type)
        affected = _find_chunk_for_offset(content.chunks, entity.start, entity.end)

        if len(affected) == 1:
            # Entity is within a single chunk — simple replacement
            idx, local_start, local_end = affected[0]
            text = chunk_texts[idx]
            chunk_texts[idx] = text[:local_start] + pseudonym + text[local_end:]

        elif len(affected) > 1:
            # Entity spans multiple chunks
            # Put the full pseudonym in the first chunk, empty the rest
            for i, (idx, local_start, local_end) in enumerate(affected):
                text = chunk_texts[idx]
                if i == 0:
                    chunk_texts[idx] = text[:local_start] + pseudonym + text[local_end:]
                else:
                    chunk_texts[idx] = text[:local_start] + text[local_end:]

    # Build new chunks with updated text
    new_chunks = []
    for i, chunk in enumerate(content.chunks):
        new_chunk = TextChunk(
            text=chunk_texts[i],
            offset=chunk.offset,
            location=dict(chunk.location),
        )
        new_chunks.append(new_chunk)

    result = DocumentContent(chunks=new_chunks, metadata=dict(content.metadata))
    result.assign_offsets()
    return result
