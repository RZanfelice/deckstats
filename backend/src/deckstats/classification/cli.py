"""Comandos do classificador.

python -m deckstats.classification.cli classify
python -m deckstats.classification.cli report [--labels tests/fixtures/category_labels.json]
"""

import argparse
import json
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from deckstats.catalog.repository import SqlCardRepository
from deckstats.classification.evaluation import evaluate
from deckstats.classification.store import iter_catalog, store_classifications
from deckstats.config import get_settings

DEFAULT_LABELS = Path("tests/fixtures/category_labels.json")


def _classify() -> None:
    engine = create_engine(get_settings().database_url)
    with Session(engine) as session, session.begin():
        result = store_classifications(session, iter_catalog(session))
    print(
        f"Classificador {result.version}: {result.cards} cartas, "
        f"{result.labeled_cards} com alguma categoria, {result.evidence_rows} evidências gravadas."
    )


def _report(labels_path: Path) -> None:
    labels = json.loads(labels_path.read_text(encoding="utf-8"))["labels"]
    engine = create_engine(get_settings().database_url)
    with Session(engine) as session:
        repository = SqlCardRepository(session)
        report = evaluate(labels, lambda name: repository.resolve([name])[0].card)
    print(f"{report.cards} cartas avaliadas; não encontradas: {report.missing or 'nenhuma'}")
    header = f"{'categoria':20} {'suporte':>7} {'TP':>4} {'FP':>4} {'FN':>4}"
    print(f"{header} {'prec':>6} {'rec':>6} {'F1':>6}")
    for category, score in report.scores.items():
        print(
            f"{category:20} {score.support:7} {score.true_positives:4} {score.false_positives:4} "
            f"{score.false_negatives:4} {score.precision:6.2f} {score.recall:6.2f} {score.f1:6.2f}"
        )
    print(f"\nmacro F1: {report.macro_f1:.3f}")
    for d in report.disagreements:
        print(f"  [{d.kind}] {d.category}: {d.card} {d.excerpt[:80]}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="deckstats.classification")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("classify", help="classifica o catálogo e grava as evidências")
    report = commands.add_parser("report", help="métricas contra o conjunto de validação")
    report.add_argument("--labels", type=Path, default=DEFAULT_LABELS)
    args = parser.parse_args(argv)

    if args.command == "classify":
        _classify()
    else:
        _report(args.labels)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
