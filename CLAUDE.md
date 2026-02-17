# Caviardeur

A CLI tool that detects and pseudonymizes PII in documents locally before sending to cloud LLMs.

Supported formats: PDF, DOCX, PPTX, XLSX, TXT, MD, JSON, XML.

## Tech Stack

- **Python 3.12** with **uv** for dependency management
- **mise** for task running and tool versioning
- **prek** for pre-commit hooks (Rust-based, uses `.pre-commit-config.yaml`)
- **ruff** for linting and formatting
- **ty** for type checking
- **pytest** + **pytest-cov** for testing (minimum 80% coverage)
- **PyInstaller** for single-binary packaging
- **release-please** for automated versioning

## Development

```bash
mise install          # Install tools (python, uv, prek)
mise run sync         # Install dependencies
mise run test         # Run tests with coverage
mise run lint         # Run ruff + ty
mise run format       # Auto-format with ruff
mise run pre-commit   # Run all pre-commit hooks
mise run build        # Build wheel/sdist
mise run package      # Build standalone binary
mise run dry-run      # Test on fixtures
```

## Conventions

- **Conventional commits are required.** All commit messages must follow the [Conventional Commits](https://www.conventionalcommits.org/) specification. This is enforced by a pre-commit hook.
  - Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`
  - Example: `feat: add XLSX reader` or `fix(cli): handle missing input directory`
- Pre-commit hooks run automatically on commit (formatting, linting, type checking, commit message validation).
- CI runs pre-commit, lint, and test on every push/PR to `main`.
