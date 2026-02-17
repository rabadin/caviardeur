from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    output_dir: Path = field(default_factory=lambda: Path("output"))
    confidence_threshold: float = 0.7
    dry_run: bool = False
    mapping_path: Path | None = None
    ner_model: str = "Jean-Baptiste/camembert-ner-with-dates"
    sliding_window_size: int = 2000
    sliding_window_overlap: int = 200
