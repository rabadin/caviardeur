from caviardeur.detectors.base import DetectedEntity, EntityType
from caviardeur.pseudonymizer.engine import pseudonymize
from caviardeur.pseudonymizer.mapping import MappingStore
from caviardeur.readers.base import DocumentContent, TextChunk


def test_pseudonymize_single_chunk():
    chunks = [TextChunk(text="Bonjour Jean Dupont, comment allez-vous?")]
    content = DocumentContent(chunks=chunks)
    content.assign_offsets()

    entities = [
        DetectedEntity(
            entity_type=EntityType.PERSON,
            text="Jean Dupont",
            start=8,
            end=19,
            confidence=0.95,
            source="ner",
        )
    ]

    mapping = MappingStore()
    result = pseudonymize(content, entities, mapping)

    assert "PERSON_001" in result.raw_text
    assert "Jean Dupont" not in result.raw_text
    assert mapping.get_real("PERSON_001") == "Jean Dupont"


def test_pseudonymize_multiple_entities():
    text = "Jean Dupont travaille chez Société Exemple SAS."
    chunks = [TextChunk(text=text)]
    content = DocumentContent(chunks=chunks)
    content.assign_offsets()

    entities = [
        DetectedEntity(
            entity_type=EntityType.PERSON,
            text="Jean Dupont",
            start=0,
            end=11,
            confidence=0.95,
            source="ner",
        ),
        DetectedEntity(
            entity_type=EntityType.COMPANY,
            text="Société Exemple SAS",
            start=27,
            end=46,
            confidence=0.87,
            source="ner",
        ),
    ]

    mapping = MappingStore()
    result = pseudonymize(content, entities, mapping)

    raw = result.raw_text
    assert "PERSON_001" in raw
    assert "COMPANY_001" in raw
    assert "Jean Dupont" not in raw
    assert "Société Exemple SAS" not in raw


def test_pseudonymize_no_entities():
    chunks = [TextChunk(text="Texte sans données personnelles.")]
    content = DocumentContent(chunks=chunks)
    content.assign_offsets()

    mapping = MappingStore()
    result = pseudonymize(content, [], mapping)
    assert result.raw_text == "Texte sans données personnelles."


def test_pseudonymize_consistent_mapping():
    text = "Jean Dupont parle à Jean Dupont."
    chunks = [TextChunk(text=text)]
    content = DocumentContent(chunks=chunks)
    content.assign_offsets()

    entities = [
        DetectedEntity(
            entity_type=EntityType.PERSON,
            text="Jean Dupont",
            start=0,
            end=11,
            confidence=0.95,
            source="ner",
        ),
        DetectedEntity(
            entity_type=EntityType.PERSON,
            text="Jean Dupont",
            start=19,
            end=30,
            confidence=0.95,
            source="ner",
        ),
    ]

    mapping = MappingStore()
    result = pseudonymize(content, entities, mapping)

    raw = result.raw_text
    assert raw.count("PERSON_001") == 2
    assert "Jean Dupont" not in raw


def test_pseudonymize_multi_chunk():
    chunks = [
        TextChunk(text="Bonjour "),
        TextChunk(text="Jean Dupont"),
        TextChunk(text=" merci"),
    ]
    content = DocumentContent(chunks=chunks)
    content.assign_offsets()

    entities = [
        DetectedEntity(
            entity_type=EntityType.PERSON,
            text="Jean Dupont",
            start=8,
            end=19,
            confidence=0.95,
            source="ner",
        )
    ]

    mapping = MappingStore()
    result = pseudonymize(content, entities, mapping)

    raw = result.raw_text
    assert "PERSON_001" in raw
    assert "Jean Dupont" not in raw
