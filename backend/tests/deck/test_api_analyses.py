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


def post_text(client: TestClient, text: str, query: str = "") -> Any:
    return client.post(
        f"/analyses/text{query}",
        content=text.encode("utf-8"),
        headers={"content-type": "text/plain; charset=utf-8"},
    )


def test_text_endpoint_accepts_the_list_pasted_as_is(client: TestClient) -> None:
    response = post_text(client, VALID)

    assert response.status_code == 200
    body = response.json()
    assert body["commanders"] == ["Atraxa, Praetors' Voice"]
    assert body["issues"] == []
    assert body["stats"]["lands"]["total"] == 99


def test_text_endpoint_matches_the_json_endpoint(client: TestClient) -> None:
    assert post_text(client, VALID).json() == post(client, VALID)


def test_text_endpoint_handles_windows_line_endings(client: TestClient) -> None:
    body = post_text(client, VALID.replace("\n", "\r\n")).json()

    assert body["issues"] == []
    assert body["stats"]["played_cards"] == 100


def test_text_endpoint_reads_the_mdfc_option_from_the_query_string(client: TestClient) -> None:
    text = "Commander\n1 Atraxa, Praetors' Voice\nDeck\n90 Forest\n9 Emeria's Call // Emeria, Shattered Skyclave\n"

    default = post_text(client, text).json()
    off = post_text(client, text, "?count_mdfc_lands=false").json()

    assert default["options"] == {"count_mdfc_lands": True}
    assert default["stats"]["lands"]["total"] == 99
    assert off["options"] == {"count_mdfc_lands": False}
    assert off["stats"]["lands"]["total"] == 90


def test_text_endpoint_rejects_empty_and_oversized_bodies(client: TestClient) -> None:
    assert post_text(client, "").status_code == 422
    assert post_text(client, "x" * 20_001).status_code == 422


def test_text_endpoint_is_documented_as_plain_text(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()

    content = schema["paths"]["/analyses/text"]["post"]["requestBody"]["content"]
    assert list(content) == ["text/plain"]


def test_json_endpoint_rejects_raw_newlines_inside_the_string(client: TestClient) -> None:
    """O que acontece ao colar uma lista no editor JSON do Swagger: use /analyses/text."""
    raw = '{"decklist": "1 Sol Ring\n1 Forest"}'

    response = client.post("/analyses", content=raw, headers={"content-type": "application/json"})

    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "json_invalid"
