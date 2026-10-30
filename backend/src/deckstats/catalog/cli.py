"""Uso: python -m deckstats.catalog.cli load [--data-dir data/raw/mtgjson]"""

import argparse
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from deckstats.catalog.loader import load_catalog
from deckstats.catalog.mtgjson import read_cards, read_source_version
from deckstats.config import get_settings

DEFAULT_DATA_DIR = Path("data/raw/mtgjson")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="deckstats.catalog")
    commands = parser.add_subparsers(dest="command", required=True)
    load = commands.add_parser("load", help="carrega o catálogo do MTGJSON no banco")
    load.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    args = parser.parse_args(argv)

    version = read_source_version(args.data_dir)
    print(f"Carregando MTGJSON {version.version} ({version.date}) de {args.data_dir} ...")
    engine = create_engine(get_settings().database_url)
    with Session(engine) as session, session.begin():
        result = load_catalog(session, read_cards(args.data_dir), version)
    print(f"Pronto: {result.cards} cartas, {result.faces} faces, {result.removed} removidas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
