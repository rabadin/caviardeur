import functools
import logging

from .base import NER_LABEL_MAP, DetectedEntity

logger = logging.getLogger(__name__)


@functools.lru_cache(maxsize=1)
def _get_pipeline(model_name: str):
    """Load the NER pipeline on first use (cached per model_name)."""
    logger.info("Loading NER model '%s' (first run downloads ~500MB)...", model_name)
    from transformers import pipeline

    pipe = pipeline(  # ty: ignore[no-matching-overload]  # "ner" is a valid alias for "token-classification"
        "ner",
        model=model_name,
        aggregation_strategy="simple",
        device=-1,  # CPU
    )
    logger.info("NER model loaded.")
    return pipe


def detect_ner(
    text: str,
    model_name: str = "Jean-Baptiste/camembert-ner-with-dates",
    confidence_threshold: float = 0.7,
    window_size: int = 2000,
    window_overlap: int = 200,
) -> list[DetectedEntity]:
    """Detect named entities using CamemBERT NER with sliding window."""
    if not text.strip():
        return []

    pipe = _get_pipeline(model_name)
    entities: list[DetectedEntity] = []
    seen_spans: set[tuple[int, int, str]] = set()

    # Sliding window to handle CamemBERT's 512-token limit
    step = window_size - window_overlap
    starts = list(range(0, len(text), step))
    if not starts:
        starts = [0]

    for window_start in starts:
        window_end = min(window_start + window_size, len(text))
        window_text = text[window_start:window_end]

        if not window_text.strip():
            continue

        results = pipe(window_text)

        for ent in results:
            label = ent["entity_group"]
            entity_type = NER_LABEL_MAP.get(label)
            if entity_type is None:
                continue

            score = ent["score"]
            if score < confidence_threshold:
                continue

            # Map back to global offsets
            global_start = window_start + ent["start"]
            global_end = window_start + ent["end"]
            ent_text = text[global_start:global_end]

            # Trim leading/trailing whitespace from entity boundaries
            stripped = ent_text.lstrip()
            if len(stripped) < len(ent_text):
                global_start += len(ent_text) - len(stripped)
            ent_text = stripped
            stripped = ent_text.rstrip()
            if len(stripped) < len(ent_text):
                global_end -= len(ent_text) - len(stripped)
            ent_text = stripped

            if not ent_text:
                continue

            # Deduplicate entities from overlapping windows
            span_key = (global_start, global_end, label)
            if span_key in seen_spans:
                continue
            seen_spans.add(span_key)

            entities.append(
                DetectedEntity(
                    entity_type=entity_type,
                    text=ent_text,
                    start=global_start,
                    end=global_end,
                    confidence=score,
                    source="ner",
                )
            )

    return entities
