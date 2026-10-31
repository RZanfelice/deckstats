import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from deckstats.catalog.loader import load_catalog
from deckstats.catalog.models import CardCategory, ClassificationRun
from deckstats.catalog.records import CardRecord, SourceVersion
from deckstats.classification import taxonomy as t
from deckstats.classification.cli import main
from deckstats.classification.store import iter_catalog, store_classifications
from deckstats.config import get_settings
from deckstats.db import Base
from tests.catalog.factories import card, face

VERSION = SourceVersion(version="5.3.0", date=date(2026, 5, 10))


def catalog_cards() -> list[CardRecord]:
    return [
        card("rock", "Sol Ring", [face("Sol Ring", text="{T}: Add {C}{C}.")]),
        card("kill", "Doom Blade", [face("Doom Blade", text="Destroy target nonblack creature.")]),
        card("bear", "Grizzly Bears", [face("Grizzly Bears", text="")]),
    ]


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        load_catalog(session, catalog_cards(), VERSION)
        session.commit()
        yield session


def rows(session: Session) -> set[tuple[str, str]]:
    return set(session.execute(select(CardCategory.oracle_id, CardCategory.category)).all())


def test_iter_catalog_visits_every_card_in_pages(session: Session) -> None:
    names = [c.name for c in iter_catalog(session, batch_size=2)]

    assert sorted(names) == ["Doom Blade", "Grizzly Bears", "Sol Ring"]


def test_iter_catalog_returns_cards_with_their_faces(session: Session) -> None:
    sol = next(c for c in iter_catalog(session) if c.name == "Sol Ring")

    assert [f.text for f in sol.faces] == ["{T}: Add {C}{C}."]


def test_store_writes_evidence_and_a_run_record(session: Session) -> None:
    result = store_classifications(session, iter_catalog(session))
    session.commit()

    assert (result.cards, result.labeled_cards) == (3, 2)
    assert result.version == t.CLASSIFIER_VERSION
    assert ("kill", t.REMOVAL) in rows(session)
    categories = {category for _, category in rows(session)}
    assert t.REMOVAL in categories
    run = session.get(ClassificationRun, t.CLASSIFIER_VERSION)
    assert run is not None
    assert (run.card_count, run.labeled_count) == (3, 2)


def test_store_keeps_the_explanation(session: Session) -> None:
    store_classifications(session, iter_catalog(session))
    session.commit()

    evidence = session.scalars(select(CardCategory).where(CardCategory.oracle_id == "kill")).one()
    assert evidence.rule == "destroy_or_exile"
    assert evidence.face == "Doom Blade"
    assert "destroy target nonblack creature" in evidence.excerpt
    assert evidence.classifier_version == t.CLASSIFIER_VERSION


def test_storing_twice_replaces_instead_of_duplicating(session: Session) -> None:
    store_classifications(session, iter_catalog(session))
    session.commit()
    first = session.scalar(select(func.count()).select_from(CardCategory))

    store_classifications(session, iter_catalog(session))
    session.commit()

    assert session.scalar(select(func.count()).select_from(CardCategory)) == first
    assert session.scalar(select(func.count()).select_from(ClassificationRun)) == 1


def test_evidence_of_other_versions_is_kept(session: Session) -> None:
    session.add(
        CardCategory(
            oracle_id="bear",
            classifier_version="rules-0.0.1",
            category=t.RAMP,
            rule="old",
            face="Grizzly Bears",
            excerpt="x",
        )
    )
    session.commit()

    store_classifications(session, iter_catalog(session))
    session.commit()

    old = session.scalars(
        select(CardCategory).where(CardCategory.classifier_version == "rules-0.0.1")
    ).all()
    assert len(old) == 1


def test_cards_without_a_category_have_no_rows(session: Session) -> None:
    store_classifications(session, iter_catalog(session))
    session.commit()

    assert "bear" not in {oracle_id for oracle_id, _ in rows(session)}


# --- CLI -----------------------------------------------------------------------------------------


@pytest.fixture
def database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    url = f"sqlite:///{tmp_path / 'catalog.db'}"
    monkeypatch.setenv("DECKSTATS_DATABASE_URL", url)
    get_settings.cache_clear()
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        load_catalog(session, catalog_cards(), VERSION)
        session.commit()
    engine.dispose()
    yield url
    get_settings.cache_clear()


def test_classify_command_stores_the_catalog(
    database: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["classify"]) == 0

    assert "3 cartas, 2 com alguma categoria" in capsys.readouterr().out
    engine = create_engine(database)
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(CardCategory)) == 2
    engine.dispose()


def test_report_command_prints_metrics(
    database: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    labels = tmp_path / "labels.json"
    labels.write_text(
        json.dumps({"labels": {"Doom Blade": ["removal"], "Sol Ring": ["ramp"], "Nope": []}}),
        encoding="utf-8",
    )

    assert main(["report", "--labels", str(labels)]) == 0

    output = capsys.readouterr().out
    assert "2 cartas avaliadas" in output
    assert "Nope" in output  # carta não encontrada é listada
    assert "macro F1" in output
