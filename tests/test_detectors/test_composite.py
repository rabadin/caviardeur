from unittest.mock import patch

from caviardeur.detectors.base import DetectedEntity, EntityType
from caviardeur.detectors.composite import _resolve_overlaps, detect_all


def _ent(etype, text, start, end, confidence=0.9, source="test"):
    return DetectedEntity(
        entity_type=etype,
        text=text,
        start=start,
        end=end,
        confidence=confidence,
        source=source,
    )


# --- _resolve_overlaps ---


def test_resolve_empty():
    assert _resolve_overlaps([]) == []


def test_resolve_no_overlaps():
    entities = [
        _ent(EntityType.PERSON, "Jean", 0, 4),
        _ent(EntityType.COMPANY, "Acme", 10, 14),
    ]
    result = _resolve_overlaps(entities)
    assert len(result) == 2


def test_resolve_overlap_higher_confidence_wins():
    low = _ent(EntityType.PERSON, "Jean Dupont", 0, 11, confidence=0.7)
    high = _ent(EntityType.PERSON, "Jean Dupont", 0, 11, confidence=0.95)
    result = _resolve_overlaps([low, high])
    assert len(result) == 1
    assert result[0].confidence == 0.95


def test_resolve_overlap_longer_span_wins():
    short = _ent(EntityType.PERSON, "Jean", 0, 4, confidence=0.9)
    long = _ent(EntityType.PERSON, "Jean Dupont", 0, 11, confidence=0.9)
    result = _resolve_overlaps([short, long])
    assert len(result) == 1
    assert result[0].text == "Jean Dupont"


def test_resolve_overlap_higher_specificity_wins():
    address = _ent(EntityType.ADDRESS, "12 rue de la Paix", 0, 17, confidence=0.9)
    person = _ent(EntityType.PERSON, "de la Paix", 7, 17, confidence=0.9)
    result = _resolve_overlaps([address, person])
    assert len(result) == 1
    assert result[0].entity_type == EntityType.ADDRESS


def test_resolve_overlap_existing_wins_when_equal_or_better():
    first = _ent(EntityType.PERSON, "Jean Dupont", 0, 11, confidence=0.95)
    second = _ent(EntityType.PERSON, "Jean", 0, 4, confidence=0.8)
    result = _resolve_overlaps([first, second])
    assert len(result) == 1
    assert result[0].text == "Jean Dupont"


def test_resolve_sorted_by_start():
    e1 = _ent(EntityType.PERSON, "Marie", 20, 25)
    e2 = _ent(EntityType.COMPANY, "Acme", 0, 4)
    result = _resolve_overlaps([e1, e2])
    assert result[0].start < result[1].start


# --- detect_all ---


@patch("caviardeur.detectors.composite.detect_ner", return_value=[])
@patch(
    "caviardeur.detectors.composite.detect_regex",
    return_value=[
        DetectedEntity(
            entity_type=EntityType.SIRET,
            text="73282932000074",
            start=0,
            end=14,
            confidence=1.0,
            source="regex",
        )
    ],
)
def test_detect_all_merges_sources(mock_regex, mock_ner):
    result = detect_all("73282932000074")
    assert len(result) == 1
    assert result[0].entity_type == EntityType.SIRET
    mock_ner.assert_called_once()
    mock_regex.assert_called_once()


@patch("caviardeur.detectors.composite.detect_ner", return_value=[])
@patch("caviardeur.detectors.composite.detect_regex", return_value=[])
def test_detect_all_empty(mock_regex, mock_ner):
    result = detect_all("nothing here")
    assert result == []
