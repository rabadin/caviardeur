# Caviardeur

Pseudonymize PII in documents locally. Each PII element is replaced with a deterministic placeholder (`PERSON_001`, `COMPANY_002`, ...) and a `mapping.json` maps placeholders back to real values. Useful for sharing documents with third parties, feeding them to cloud LLMs, or archiving sanitized copies.

## Install

Download the latest binary for your platform from the GitHub Releases page and run it directly:

```bash
chmod +x caviardeur-*    # macOS/Linux only
./caviardeur-v0.1.0-macos-arm64 --help
```

The CamemBERT NER model (~500MB) is downloaded automatically on first run.


## Usage

```bash
# Process a file or directory
caviardeur ./documents/ -o ./anonymized/

# Preview detections without writing anything
caviardeur ./documents/ --dry-run

# Adjust NER confidence threshold
caviardeur ./contract.pdf -o ./out/ -c 0.8

# Reuse mapping from a previous run for cross-batch consistency
caviardeur ./batch2/ -o ./out2/ -m ./out1/mapping.json
```

### Options

| Flag | Description | Default |
|------|-------------|---------|
| `<input>` | File or directory to process | (required) |
| `-o`, `--output` | Output directory for anonymized files | `./output/` |
| `--dry-run` | Show detections without writing files | `false` |
| `-c`, `--confidence` | NER confidence threshold (0.0-1.0) | `0.7` |
| `-m`, `--mapping` | Path to existing `mapping.json` for cross-batch consistency | none |
| `-v`, `--verbose` | Verbose logging | `false` |

## Supported Formats

| Format | Read | Write | Notes |
|--------|------|-------|-------|
| .txt, .md, .json, .xml | yes | yes | UTF-8, fallback latin-1 |
| .docx | yes | yes | Run-level extraction preserves formatting |
| .pptx | yes | yes | Run-level extraction preserves formatting |
| .xlsx | yes | yes | Cell-level replacement, formatting preserved |
| .xls | yes | .xlsx | Read-only format; output converted to .xlsx |
| .pdf | yes | yes | Redaction-based: whitewash original, overlay pseudonym |
| .doc, .ppt | no | - | Warning logged; convert to .docx/.pptx first |
| Scanned PDF | no | - | Detected (no extractable text) and warned |

## How Does It Work?

Caviardeur reads a document, extracts its text while preserving structure (paragraphs, cells, PDF spans), then runs two detection passes over it:

1. **Named Entity Recognition** — a [CamemBERT NER model](https://huggingface.co/Jean-Baptiste/camembert-ner-with-dates) (a French BERT variant, ~500MB) identifies person names (F1 0.959), company names (F1 0.865), and locations (F1 0.931). A sliding window handles documents longer than the model's 512-token limit.

2. **Regex patterns** — SIRET numbers are matched with a 14-digit pattern validated by Luhn checksum. French addresses are matched by street type keywords (rue, avenue, boulevard, ...) combined with postal code patterns.

Results from both passes are merged. When two detections overlap, the one with higher confidence, longer span, or more specific type wins. Each unique entity gets a stable placeholder (`PERSON_001`, `COMPANY_001`, `SIRET_001`, `ADDRESS_001`, ...) and the document is rewritten with these placeholders in place of the original text, preserving the original formatting.

## Mapping File

The output directory contains a `mapping.json`:

```json
{
  "PERSON_001": "Jean Dupont",
  "PERSON_002": "Marie Laurent",
  "COMPANY_001": "Societe Exemple SAS",
  "SIRET_001": "123 456 789 01234",
  "ADDRESS_001": "12 rue de la Paix, 75002 Paris"
}
```

Pass it to subsequent runs with `-m` to keep pseudonyms consistent across batches.

## Consistency Guarantees

- **Same text, same pseudonym**: "Jean Dupont" always maps to the same placeholder within and across batches (when using `-m`)
- **Normalization**: Whitespace is collapsed and matching is case-insensitive
- **Deterministic**: No randomness. Same input always produces the same output.

## Development

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
git clone <repo-url> && cd caviardeur
uv sync
uv run caviardeur --help
```

[mise](https://mise.jdx.dev/) is used for task running:

```bash
mise run test           # Run test suite
mise run test:cov       # Run tests with coverage
mise run lint           # Run ruff linter
mise run format         # Format code with ruff
mise run dry-run        # Dry-run on test fixtures
mise run package        # Build single-file executable with PyInstaller
mise run clean          # Remove build artifacts
```

## Building a Standalone Executable

```bash
mise run package
```

Produces a single-file binary at `dist/caviardeur` (macOS/Linux) or `dist/caviardeur.exe` (Windows). The binary bundles Python and all libraries but the CamemBERT model is still downloaded on first run.

Releases are automated via [release-please](https://github.com/googleapis/release-please). Pushing conventional commits to `main` opens a Release PR; merging it creates a GitHub Release with binaries for Linux (amd64), macOS (arm64), and Windows (amd64).

## Known Limitations

- **No .doc support** - legacy binary format requires LibreOffice. Convert to .docx first.
- **No scanned PDF** - requires OCR. Detected (empty text extraction) and warned.
- **No partial name matching** - "M. Dupont" and "Jean Dupont" get separate pseudonyms.
- **Entity spanning DOCX runs** - if a name is split across runs with different formatting, the replacement may alter the second run's formatting.
- **PDF text overflow** - if a pseudonym is longer than the original text, it may overflow the bounding box. Rare since pseudonyms are short.

## Tech Stack

- **Python 3.12** (pinned for PyTorch wheel compatibility)
- **CamemBERT NER** via HuggingFace `transformers` (~500MB model, ~1-2GB RAM)
- **PyMuPDF** for PDF, **python-docx** for Word, **openpyxl**/**xlrd** for Excel
- **Click** + **Rich** for CLI
- **PyInstaller** for standalone executables
- **uv** for dependency management, **mise** for task running
