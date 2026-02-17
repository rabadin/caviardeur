from caviardeur.detectors.base import EntityType
from caviardeur.detectors.regex_detector import (
    _luhn_check,
    detect_addresses,
    detect_siret,
)

# --- Luhn checksum ---


def test_luhn_valid():
    # Known valid SIRET: 732 829 320 00074
    assert _luhn_check("73282932000074") is True


def test_luhn_invalid():
    assert _luhn_check("12345678901234") is False


# --- SIRET detection ---


def test_detect_siret_valid_no_spaces():
    entities = detect_siret("Le SIRET est 73282932000074 pour cette entreprise.")
    assert len(entities) == 1
    assert entities[0].entity_type == EntityType.SIRET
    assert entities[0].text == "73282932000074"


def test_detect_siret_valid_with_spaces():
    entities = detect_siret("SIRET: 732 829 320 00074")
    assert len(entities) == 1
    assert entities[0].text == "732 829 320 00074"


def test_detect_siret_invalid_checksum():
    entities = detect_siret("SIRET: 12345678901234")
    assert len(entities) == 0


def test_detect_siret_wrong_length():
    entities = detect_siret("Numéro: 1234567890")
    assert len(entities) == 0


# --- French address detection ---


def test_detect_address_simple():
    entities = detect_addresses("Adresse: 12 rue de la Paix, 75002 Paris")
    assert len(entities) == 1
    assert entities[0].entity_type == EntityType.ADDRESS
    assert "rue de la Paix" in entities[0].text


def test_detect_address_boulevard():
    entities = detect_addresses("Siège: 45 boulevard Haussmann, 75009 Paris")
    assert len(entities) == 1
    assert "boulevard Haussmann" in entities[0].text


def test_detect_address_avenue():
    entities = detect_addresses("Bureau: 8 avenue des Champs-Élysées")
    assert len(entities) == 1
    assert "avenue des Champs" in entities[0].text


def test_detect_address_no_match():
    entities = detect_addresses("Ceci est un texte sans adresse.")
    assert len(entities) == 0
