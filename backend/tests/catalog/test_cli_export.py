from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from deckstats.catalog.cli import main
from deckstats.catalog.repository import SqlCardRepository
from tests.catalog.builders import Dataset


def test_export_sqlite_creates_a_queryable_catalog(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dataset = Dataset()
    dataset.add_printing("sol", name="Sol Ring")
    dataset.add_printing("island", name="Island", types="Land")
    data_dir = dataset.write(tmp_path / "mtgjson")
    output = tmp_path / "out" / "catalog.sqlite"

    assert main(["export-sqlite", "--data-dir", str(data_dir), "--output", str(output)]) == 0

    assert "2 cartas, 2 faces" in capsys.readouterr().out
    engine = create_engine(f"sqlite:///{output}")
    with Session(engine) as session:
        result = SqlCardRepository(session).resolve(["sol ring"])[0]
    assert result.card is not None
    assert result.card.name == "Sol Ring"
    engine.dispose()


def test_export_sqlite_replaces_a_previous_file(tmp_path: Path) -> None:
    dataset = Dataset()
    dataset.add_printing("sol", name="Sol Ring")
    data_dir = dataset.write(tmp_path / "mtgjson")
    output = tmp_path / "catalog.sqlite"

    main(["export-sqlite", "--data-dir", str(data_dir), "--output", str(output)])
    first_size = output.stat().st_size
    main(["export-sqlite", "--data-dir", str(data_dir), "--output", str(output)])

    assert output.stat().st_size == first_size
