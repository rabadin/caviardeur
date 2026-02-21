import logging
from importlib.metadata import version
from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .config import Config
from .pipeline import process_file
from .pseudonymizer.mapping import MappingStore
from .readers.registry import list_supported_files

logger = logging.getLogger(__name__)

console = Console()


@click.command()
@click.argument("input_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "-o",
    "--output",
    "output_dir",
    type=click.Path(path_type=Path),
    default="output",
    help="Output directory for anonymized files.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show detections without writing files.",
)
@click.option(
    "-c",
    "--confidence",
    type=float,
    default=0.7,
    show_default=True,
    help="NER confidence threshold (0.0–1.0).",
)
@click.option(
    "-m",
    "--mapping",
    "mapping_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to existing mapping.json for cross-batch consistency.",
)
@click.option("-v", "--verbose", is_flag=True, default=False, help="Verbose logging.")
@click.version_option(version=version("caviardeur"))
def main(
    input_path: Path,
    output_dir: Path,
    dry_run: bool,
    confidence: float,
    mapping_path: Path | None,
    verbose: bool,
) -> None:
    """Pseudonymize PII in documents.

    INPUT_PATH can be a single file or a directory of documents.
    Supported formats: .txt, .md, .json, .xml, .docx, .xlsx, .xls, .pdf, .pptx
    """
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(message)s",
    )

    config = Config(
        output_dir=output_dir,
        confidence_threshold=confidence,
        dry_run=dry_run,
        mapping_path=mapping_path,
    )

    # Load or create mapping
    if mapping_path and mapping_path.exists():
        console.print(f"Loading existing mapping from {mapping_path}")
        mapping = MappingStore.load(mapping_path)
    else:
        mapping = MappingStore()

    # Discover files
    files = list_supported_files(input_path)
    if not files:
        console.print("[red]No supported files found.[/red]")
        raise SystemExit(1)

    console.print(f"Found {len(files)} file(s) to process")

    if dry_run:
        console.print("[yellow]Dry run — no files will be written.[/yellow]")
    else:
        config.output_dir.mkdir(parents=True, exist_ok=True)

    # Process files
    total_entities = 0
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Processing...", total=len(files))
        for file_path in files:
            progress.update(task, description=f"Processing {file_path.name}...")
            try:
                entities = process_file(file_path, config, mapping, console=console)
                total_entities += len(entities)
            except Exception:
                console.print(f"  [red]Error processing {file_path.name}[/red]")
                logger.debug("Failed to process %s", file_path.name, exc_info=True)
            progress.advance(task)

    # Summary
    console.print()
    console.print(f"[bold green]Done.[/bold green] {total_entities} PII entities detected across {len(files)} file(s).")

    if not dry_run and total_entities > 0:
        mapping_out = config.output_dir / "mapping.json"
        mapping.save(mapping_out)
        console.print(f"Mapping saved to {mapping_out}")
        console.print(f"Anonymized files in {config.output_dir}/")
