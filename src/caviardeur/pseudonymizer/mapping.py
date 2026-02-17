import contextlib
import json
import os
import re
from pathlib import Path

from ..detectors.base import EntityType

# Prefix for each entity type
_PREFIX_MAP: dict[EntityType, str] = {
    EntityType.PERSON: "PERSON",
    EntityType.COMPANY: "COMPANY",
    EntityType.ADDRESS: "ADDRESS",
    EntityType.SIRET: "SIRET",
}


def _normalize(text: str) -> str:
    """Normalize text for consistent matching: collapse whitespace, strip."""
    return re.sub(r"\s+", " ", text.strip())


class MappingStore:
    """Bidirectional mapping between real PII values and pseudonyms."""

    def __init__(self) -> None:
        # pseudonym -> real value
        self._pseudo_to_real: dict[str, str] = {}
        # normalized real value -> pseudonym
        self._real_to_pseudo: dict[str, str] = {}
        # Counter per entity type
        self._counters: dict[EntityType, int] = {t: 0 for t in EntityType}

    def get_or_create(self, real_text: str, entity_type: EntityType) -> str:
        """Get existing pseudonym or create a new one for the given text."""
        normalized = _normalize(real_text)
        key = f"{entity_type.value}::{normalized.lower()}"

        if key in self._real_to_pseudo:
            return self._real_to_pseudo[key]

        # Create new pseudonym
        self._counters[entity_type] += 1
        prefix = _PREFIX_MAP[entity_type]
        pseudonym = f"{prefix}_{self._counters[entity_type]:03d}"

        self._pseudo_to_real[pseudonym] = real_text
        self._real_to_pseudo[key] = pseudonym
        return pseudonym

    def get_real(self, pseudonym: str) -> str | None:
        """Look up the real value for a pseudonym."""
        return self._pseudo_to_real.get(pseudonym)

    def get_pseudonym(self, real_text: str, entity_type: EntityType) -> str | None:
        """Look up an existing pseudonym for a real value."""
        normalized = _normalize(real_text)
        key = f"{entity_type.value}::{normalized.lower()}"
        return self._real_to_pseudo.get(key)

    @property
    def mapping(self) -> dict[str, str]:
        """Return the pseudonym -> real value mapping."""
        return dict(self._pseudo_to_real)

    def save(self, path: Path) -> None:
        """Save mapping to a JSON file with restricted permissions (contains PII)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._pseudo_to_real, f, ensure_ascii=False, indent=2)
        with contextlib.suppress(OSError):
            os.chmod(path, 0o600)

    @classmethod
    def load(cls, path: Path) -> "MappingStore":
        """Load a mapping from a JSON file for cross-batch consistency."""
        store = cls()
        with open(path, encoding="utf-8") as f:
            data: dict[str, str] = json.load(f)

        for pseudonym, real_value in data.items():
            # Parse the pseudonym to extract entity type and counter
            parts = pseudonym.rsplit("_", 1)
            if len(parts) != 2:
                continue

            prefix, counter_str = parts
            try:
                counter = int(counter_str)
            except ValueError:
                continue

            # Find matching entity type
            entity_type = None
            for et, p in _PREFIX_MAP.items():
                if p == prefix:
                    entity_type = et
                    break

            if entity_type is None:
                continue

            normalized = _normalize(real_value)
            key = f"{entity_type.value}::{normalized.lower()}"

            store._pseudo_to_real[pseudonym] = real_value
            store._real_to_pseudo[key] = pseudonym
            store._counters[entity_type] = max(store._counters[entity_type], counter)

        return store
