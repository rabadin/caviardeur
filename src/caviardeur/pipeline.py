import logging
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .config import Config
from .detectors.base import DetectedEntity
from .detectors.composite import detect_all
from .pseudonymizer.engine import pseudonymize
from .pseudonymizer.mapping import MappingStore
from .readers.base import DocumentContent
from .readers.registry import read_document
from .writers.docx_writer import write_docx
from .writers.excel_writer import write_xlsx
from .writers.pdf_writer import write_pdf
from .writers.pptx_writer import write_pptx
from .writers.txt_writer import write_txt

logger = logging.getLogger(__name__)

WRITERS = {
    ".txt": write_txt,
    ".md": write_txt,
    ".json": write_txt,
    ".xml": write_txt,
    ".docx": write_docx,
    ".xlsx": write_xlsx,
    ".pdf": write_pdf,
    ".pptx": write_pptx,
}


def _write_document(content: DocumentContent, output_path: Path, source_path: Path) -> None:
    """Write a pseudonymized document using the appropriate writer."""
    ext = output_path.suffix.lower()
    writer = WRITERS.get(ext)
    if writer is None:
        logger.warning("No writer for format: %s", ext)
        return
    writer(content, output_path, source_path)


def _display_detections(file_name: str, entities: list[DetectedEntity], console: Console) -> None:
    """Display detected entities in a rich table."""
    if not entities:
        console.print(f"  [dim]{file_name}: no PII detected[/dim]")
        return

    table = Table(title=f"{file_name}", show_lines=False, padding=(0, 1))
    table.add_column("Type", style="cyan", width=10)
    table.add_column("Text", style="yellow")
    table.add_column("Confidence", style="green", width=10)
    table.add_column("Source", style="dim", width=6)

    for entity in entities:
        # Truncate long texts for display
        display_text = entity.text if len(entity.text) <= 60 else entity.text[:57] + "..."
        table.add_row(
            entity.entity_type.value,
            display_text,
            f"{entity.confidence:.2f}",
            entity.source,
        )

    console.print(table)


def process_file(
    file_path: Path,
    config: Config,
    mapping: MappingStore,
    *,
    console: Console | None = None,
) -> list[DetectedEntity]:
    """Process a single file through the full pipeline.

    Returns the list of detected entities.
    """
    if console is None:
        console = Console()

    logger.info("Reading: %s", file_path.name)

    # 1. Read
    content = read_document(file_path)
    if content is None:
        return []

    raw_text = content.raw_text
    if not raw_text.strip():
        logger.info("  No text content in %s, skipping.", file_path.name)
        return []

    # 2. Detect
    entities = detect_all(
        raw_text,
        model_name=config.ner_model,
        confidence_threshold=config.confidence_threshold,
        window_size=config.sliding_window_size,
        window_overlap=config.sliding_window_overlap,
    )

    # 3. Display detections
    _display_detections(file_path.name, entities, console)

    if config.dry_run or not entities:
        return entities

    # 4. Pseudonymize
    anonymized = pseudonymize(content, entities, mapping)

    # 5. Write
    source_path = Path(content.metadata["source_path"])
    output_name = file_path.name
    # xls -> xlsx conversion
    if content.metadata.get("format") == "xls":
        output_name = file_path.stem + ".xlsx"
    output_path = config.output_dir / output_name

    _write_document(anonymized, output_path, source_path)
    logger.info("  Written: %s", output_path)

    return entities
