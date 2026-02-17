from pathlib import Path

from caviardeur.detectors.base import EntityType
from caviardeur.pseudonymizer.mapping import MappingStore


def test_get_or_create_new():
    store = MappingStore()
    result = store.get_or_create("Jean Dupont", EntityType.PERSON)
    assert result == "PERSON_001"


def test_get_or_create_same_text_returns_same():
    store = MappingStore()
    r1 = store.get_or_create("Jean Dupont", EntityType.PERSON)
    r2 = store.get_or_create("Jean Dupont", EntityType.PERSON)
    assert r1 == r2 == "PERSON_001"


def test_get_or_create_different_texts():
    store = MappingStore()
    r1 = store.get_or_create("Jean Dupont", EntityType.PERSON)
    r2 = store.get_or_create("Marie Laurent", EntityType.PERSON)
    assert r1 == "PERSON_001"
    assert r2 == "PERSON_002"


def test_get_or_create_different_types():
    store = MappingStore()
    r1 = store.get_or_create("Acme Corp", EntityType.COMPANY)
    r2 = store.get_or_create("Jean Dupont", EntityType.PERSON)
    assert r1 == "COMPANY_001"
    assert r2 == "PERSON_001"


def test_normalization_whitespace():
    store = MappingStore()
    r1 = store.get_or_create("Jean  Dupont", EntityType.PERSON)
    r2 = store.get_or_create("Jean Dupont", EntityType.PERSON)
    assert r1 == r2


def test_normalization_case_insensitive():
    store = MappingStore()
    r1 = store.get_or_create("jean dupont", EntityType.PERSON)
    r2 = store.get_or_create("Jean Dupont", EntityType.PERSON)
    assert r1 == r2


def test_get_real():
    store = MappingStore()
    store.get_or_create("Jean Dupont", EntityType.PERSON)
    assert store.get_real("PERSON_001") == "Jean Dupont"
    assert store.get_real("PERSON_999") is None


def test_get_pseudonym():
    store = MappingStore()
    store.get_or_create("Jean Dupont", EntityType.PERSON)
    assert store.get_pseudonym("Jean Dupont", EntityType.PERSON) == "PERSON_001"
    assert store.get_pseudonym("Unknown", EntityType.PERSON) is None


def test_mapping_property():
    store = MappingStore()
    store.get_or_create("Jean Dupont", EntityType.PERSON)
    store.get_or_create("Acme Corp", EntityType.COMPANY)
    m = store.mapping
    assert m == {"PERSON_001": "Jean Dupont", "COMPANY_001": "Acme Corp"}


def test_save_and_load(tmp_path: Path):
    store = MappingStore()
    store.get_or_create("Jean Dupont", EntityType.PERSON)
    store.get_or_create("Marie Laurent", EntityType.PERSON)
    store.get_or_create("Acme Corp", EntityType.COMPANY)
    store.get_or_create("123 456 789 00018", EntityType.SIRET)

    path = tmp_path / "mapping.json"
    store.save(path)

    loaded = MappingStore.load(path)
    assert loaded.mapping == store.mapping

    # Verify counters are restored — next created should continue from max
    r = loaded.get_or_create("Pierre Martin", EntityType.PERSON)
    assert r == "PERSON_003"

    # Verify existing entries are found
    r = loaded.get_or_create("Jean Dupont", EntityType.PERSON)
    assert r == "PERSON_001"
