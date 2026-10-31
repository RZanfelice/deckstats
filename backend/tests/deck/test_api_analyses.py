from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from deckstats.api.deps import get_card_repository
from deckstats.catalog.repository import CardRepository, SqlCardRepository
from deckstats.main import create_app

VALID = "Commander\n1 Atraxa, Praetors' Voice\n\nDeck\n99 Forest\n"


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    app = create_app()

    def override() -> Iterator[CardRepository]:
        with Session(engine) as session:
            yield SqlCardRepository(session)

    app.dependency_overrides[get_card_repository] = override
    yield TestClient(app)


def post(client: TestClient, decklist: str, **options: object) -> dict[str, Any]:
    response = client.post("/analyses", json={"decklist": decklist, "options": options})
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_analysis_response_shape(client: TestClient) -> None:
    body = post(client, VALID)

    assert body["format"] == "commander"
    assert body["commanders"] == ["Atraxa, Praetors' Voice"]
    assert body["commander_inferred"] is False
    assert body["issues"] == []
    assert body["unresolved"] == []
    assert body["stats"]["lands"] == {"lands": 99, "mdfc_lands": 0, "total": 99}
    assert body["stats"]["curve"]["0"] == 0
    assert body["stats"]["average_mana_value"] is None
    assert body["stats"]["commander_mana_values"] == [4.0]
    assert {card["name"] for card in body["cards"]} == {"Atraxa, Praetors' Voice", "Forest"}


def test_issues_carry_codes_and_data_not_prose(client: TestClient) -> None:
    body = post(client, VALID + "1 Solring\n")

    assert body["issues"][0] == {
        "code": "cards_not_found",
        "severity": "error",
        "cards": ["Solring"],
        "details": {},
    }
    assert body["unresolved"][0]["suggestions"][0] == "Sol Ring"


def test_mdfc_option_is_configurable_and_on_by_default(client: TestClient) -> None:
    text = "Commander\n1 Atraxa, Praetors' Voice\nDeck\n90 Forest\n9 Emeria's Call // Emeria, Shattered Skyclave\n"

    default = post(client, text)
    off = post(client, text, count_mdfc_lands=False)

    assert default["options"] == {"count_mdfc_lands": True}
    assert default["stats"]["lands"]["total"] == 99
    assert off["options"] == {"count_mdfc_lands": False}
    assert off["stats"]["lands"]["total"] == 90


@pytest.mark.parametrize("payload", [{}, {"decklist": ""}, {"decklist": "x" * 20_001}])
def test_invalid_requests_are_rejected(client: TestClient, payload: dict[str, object]) -> None:
    assert client.post("/analyses", json=payload).status_code == 422


def test_openapi_documents_the_endpoint(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()

    assert "/analyses" in schema["paths"]
    assert "AnalysisResponse" in schema["components"]["schemas"]
