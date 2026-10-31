"""O classificador contra o conjunto-semente rotulado à mão (item 4.4).

Roda contra o catálogo real (pulado sem data/catalog.sqlite). Os limiares travam o
desempenho atual como piso contra regressões; não são uma meta.
"""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from deckstats.catalog.repository import SqlCardRepository
from deckstats.classification import taxonomy as t
from deckstats.classification.evaluation import Report, evaluate

ROOT = Path(__file__).resolve().parents[3]
CATALOG = ROOT / "data" / "catalog.sqlite"
LABELS = Path(__file__).resolve().parents[1] / "fixtures" / "category_labels.json"

pytestmark = pytest.mark.skipif(not CATALOG.exists(), reason="data/catalog.sqlite não existe")

# Divergências ambíguas conhecidas, que não foram "corrigidas" no gabarito (ver _corrections).
KNOWN_BORDERLINE = {
    ("Goldspan Dragon", t.RAMP),
    ("Goblin Bombardment", t.REMOVAL),
    ("Goblin Bombardment", t.INTERACTION),
}


@pytest.fixture(scope="module")
def report() -> Iterator[Report]:
    labels = json.loads(LABELS.read_text(encoding="utf-8"))["labels"]
    engine = create_engine(f"sqlite:///{CATALOG}")
    with Session(engine) as session:
        repository = SqlCardRepository(session)
        yield evaluate(labels, lambda name: repository.resolve([name])[0].card)
    engine.dispose()


def test_every_labeled_card_exists_in_the_catalog(report: Report) -> None:
    assert report.missing == []
    assert report.cards >= 150


def test_macro_f1_is_high(report: Report) -> None:
    assert report.macro_f1 >= 0.97


@pytest.mark.parametrize("category", t.SUPPORTED)
def test_each_category_holds_its_floor(report: Report, category: str) -> None:
    score = report.scores[category]

    assert score.support > 0
    assert score.f1 >= 0.9, (category, score)
    assert score.recall >= 0.95, (category, score)


def test_the_only_disagreements_are_the_known_borderline_cases(report: Report) -> None:
    unexpected = [
        (d.card, d.category, d.kind)
        for d in report.disagreements
        if (d.card, d.category) not in KNOWN_BORDERLINE
    ]

    assert unexpected == []


def test_combo_piece_is_not_scored() -> None:
    labels = json.loads(LABELS.read_text(encoding="utf-8"))["labels"]

    assert all(t.COMBO_PIECE not in categories for categories in labels.values())
