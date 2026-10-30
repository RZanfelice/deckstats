from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from deckstats.catalog.cli import main
from deckstats.catalog.models import CardFace, OracleCard
from deckstats.config import get_settings
from deckstats.db import Base
from tests.catalog.builders import Dataset


def test_load_command_populates_the_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    database = tmp_path / "catalog.db"
    monkeypatch.setenv("DECKSTATS_DATABASE_URL", f"sqlite:///{database}")
    get_settings.cache_clear()
    engine = create_engine(f"sqlite:///{database}")
    Base.metadata.create_all(engine)

    dataset = Dataset()
    dataset.add_printing("sol", name="Sol Ring")
    dataset.add_printing("island", name="Island", types="Land")
    data_dir = dataset.write(tmp_path / "mtgjson")

    exit_code = main(["load", "--data-dir", str(data_dir)])

    assert exit_code == 0
    assert "2 cartas, 2 faces, 0 removidas" in capsys.readouterr().out
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(OracleCard)) == 2
        assert session.scalar(select(func.count()).select_from(CardFace)) == 2
    get_settings.cache_clear()
