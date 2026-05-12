"""Shared test fixtures for kr_finance_kit."""
from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture()
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture()
def opendart_sample(fixtures_dir: Path) -> str:
    return (fixtures_dir / "opendart_sample.json").read_text(encoding="utf-8")
