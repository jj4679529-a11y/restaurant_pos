"""Persistent deployment paths; no database or secret dependencies."""
from pathlib import Path


def configuration_file(application_directory: Path) -> Path:
    # Preserve legacy adjacent .env deployments. Never move or overwrite either file.
    adjacent = application_directory / '.env'
    separated = application_directory.parent / 'config' / '.env'
    if adjacent.is_file() or application_directory.name.casefold() != 'app':
        return adjacent
    return separated
