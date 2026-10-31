"""Comandos do catálogo.

python -m deckstats.catalog.cli load [--data-dir data/raw/mtgjson]
python -m deckstats.catalog.cli export-sqlite [--data-dir ...] [--output data/catalog.sqlite]
"""

import argparse
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from deckstats.catalog.loader import load_catalog
from deckstats.catalog.mtgjson import read_cards, read_source_version
from deckstats.config import get_settings
from deckstats.db import Base

DEFAULT_DATA_DIR = Path("data/raw/mtgjson")
DEFAULT_SQLITE_OUTPUT = Path("data/catalog.sqlite")


def _load(data_dir: Path) -> None:
    version = read_source_version(data_dir)
    print(f"Carregando MTGJSON {version.version} ({version.date}) de {data_dir} ...")
    engine = create_engine(get_settings().database_url)
    with Session(engine) as session, session.begin():
        result = load_catalog(session, read_cards(data_dir), version)
    print(f"Pronto: {result.cards} cartas, {result.faces} faces, {result.removed} removidas.")


def _export_sqlite(data_dir: Path, output: Path) -> None:
    """Gera um SQLite novo do zero, pronto para a demo enxuta (sem Postgres)."""
    version = read_source_version(data_dir)
    print(f"Exportando MTGJSON {version.version} para {output} ...")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.unlink(missing_ok=True)
    engine = create_engine(f"sqlite:///{output}")
    Base.metadata.create_all(engine)
    with Session(engine) as session, session.begin():
        result = load_catalog(session, read_cards(data_dir), version)
    engine.dispose()
    size_mb = output.stat().st_size / 1_000_000
    print(f"Pronto: {result.cards} cartas, {result.faces} faces, {size_mb:.1f} MB.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="deckstats.catalog")
    commands = parser.add_subparsers(dest="command", required=True)

    load = commands.add_parser("load", help="carrega o catálogo do MTGJSON no banco")
    load.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)

    export = commands.add_parser("export-sqlite", help="gera o catálogo em um arquivo SQLite")
    export.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    export.add_argument("--output", type=Path, default=DEFAULT_SQLITE_OUTPUT)

    args = parser.parse_args(argv)
    if args.command == "load":
        _load(args.data_dir)
    else:
        _export_sqlite(args.data_dir, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
