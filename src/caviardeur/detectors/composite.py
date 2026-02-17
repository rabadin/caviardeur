from .base import DetectedEntity
from .ner_detector import detect_ner
from .regex_detector import detect_regex


def _resolve_overlaps(entities: list[DetectedEntity]) -> list[DetectedEntity]:
    """Resolve overlapping entity detections.

    When two entities overlap, prefer:
    1. Higher confidence
    2. Longer span
    3. More specific type (SIRET > ADDRESS > PERSON/COMPANY)
    """
    if not entities:
        return []

    # Sort by start position, then by length descending
    entities.sort(key=lambda e: (e.start, -(e.end - e.start)))

    specificity = {"SIRET": 3, "ADDRESS": 2, "PERSON": 1, "COMPANY": 1}

    def _score(e: DetectedEntity) -> tuple:
        return (
            e.confidence,
            e.end - e.start,
            specificity.get(e.entity_type.value, 0),
        )

    resolved: list[DetectedEntity] = []
    for entity in entities:
        overlapping = [a for a in resolved if entity.overlaps(a)]

        if not overlapping:
            resolved.append(entity)
            continue

        # Only replace if the new entity beats every overlapping entity
        if all(_score(entity) > _score(a) for a in overlapping):
            for a in overlapping:
                resolved.remove(a)
            resolved.append(entity)

    # Sort by start position for consistent output
    resolved.sort(key=lambda e: e.start)
    return resolved


def detect_all(
    text: str,
    model_name: str = "Jean-Baptiste/camembert-ner-with-dates",
    confidence_threshold: float = 0.7,
    window_size: int = 2000,
    window_overlap: int = 200,
) -> list[DetectedEntity]:
    """Run all detectors and merge results."""
    ner_entities = detect_ner(
        text,
        model_name=model_name,
        confidence_threshold=confidence_threshold,
        window_size=window_size,
        window_overlap=window_overlap,
    )
    regex_entities = detect_regex(text)

    all_entities = ner_entities + regex_entities
    return _resolve_overlaps(all_entities)
