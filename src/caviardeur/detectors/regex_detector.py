import re

from .base import DetectedEntity, EntityType

# SIRET: 14 digits, optionally space-separated in groups
_SIRET_PATTERN = re.compile(r"\b(\d{3})\s?(\d{3})\s?(\d{3})\s?(\d{5})\b")

# French address: street type keyword + street name, optional postal code + city
_STREET_TYPES = (
    r"(?:rue|avenue|boulevard|place|allée|chemin|impasse|passage|cours|quai|route"
    r"|av\.|bd\.|pl\.)"
)
_ADDRESS_PATTERN = re.compile(
    rf"\b\d{{1,4}}(?:\s*(?:bis|ter))?\s*,?\s*{_STREET_TYPES}\s+[A-ZÀ-Ü][\w\s\-']{{2,50}}"
    rf"(?:\s*,?\s*\d{{5}}\s+[A-ZÀ-Ü][\w\s\-']{{2,30}})?",
    re.IGNORECASE,
)


def _luhn_check(digits: str) -> bool:
    """Validate a digit string using the Luhn algorithm."""
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def detect_siret(text: str) -> list[DetectedEntity]:
    """Detect SIRET numbers (14 digits + Luhn checksum)."""
    entities = []
    for m in _SIRET_PATTERN.finditer(text):
        digits = "".join(m.groups())
        if len(digits) == 14 and _luhn_check(digits):
            entities.append(
                DetectedEntity(
                    entity_type=EntityType.SIRET,
                    text=m.group(),
                    start=m.start(),
                    end=m.end(),
                    confidence=0.95,
                    source="regex",
                )
            )
    return entities


def detect_addresses(text: str) -> list[DetectedEntity]:
    """Detect French addresses using regex patterns."""
    entities = []
    for m in _ADDRESS_PATTERN.finditer(text):
        entities.append(
            DetectedEntity(
                entity_type=EntityType.ADDRESS,
                text=m.group(),
                start=m.start(),
                end=m.end(),
                confidence=0.75,
                source="regex",
            )
        )
    return entities


def detect_regex(text: str) -> list[DetectedEntity]:
    """Run all regex-based detectors."""
    return detect_siret(text) + detect_addresses(text)
