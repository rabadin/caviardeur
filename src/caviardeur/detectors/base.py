from dataclasses import dataclass
from enum import Enum


class EntityType(Enum):
    PERSON = "PERSON"
    COMPANY = "COMPANY"
    ADDRESS = "ADDRESS"
    SIRET = "SIRET"


# Map CamemBERT NER labels to our entity types
NER_LABEL_MAP: dict[str, EntityType] = {
    "PER": EntityType.PERSON,
    "ORG": EntityType.COMPANY,
    "LOC": EntityType.ADDRESS,
}


@dataclass
class DetectedEntity:
    """A PII entity detected in text."""

    entity_type: EntityType
    text: str
    start: int  # Character offset in raw_text
    end: int  # Character offset in raw_text (exclusive)
    confidence: float = 1.0
    source: str = ""  # "ner" or "regex"

    @property
    def span(self) -> tuple[int, int]:
        return (self.start, self.end)

    def overlaps(self, other: "DetectedEntity") -> bool:
        return self.start < other.end and other.start < self.end
