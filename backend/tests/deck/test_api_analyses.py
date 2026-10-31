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

    assert default["options"] == {
        "count_mdfc_lands": True,
        "commander_weight": 0.6,
        "on_the_play": False,
    }
    assert default["stats"]["lands"]["total"] == 99
    assert off["options"] == {
        "count_mdfc_lands": False,
        "commander_weight": 0.6,
        "on_the_play": False,
    }
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

    assert default["options"] == {
        "count_mdfc_lands": True,
        "commander_weight": 0.6,
        "on_the_play": False,
    }
    assert default["stats"]["lands"]["total"] == 99
    assert off["options"] == {
        "count_mdfc_lands": False,
        "commander_weight": 0.6,
        "on_the_play": False,
    }
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


MIXED = "Commander\n1 Atraxa, Praetors' Voice\nDeck\n36 Forest\n63 Cultivate\n"


def test_response_includes_the_land_odds_and_critical_turn(client: TestClient) -> None:
    odds = post(client, MIXED)["land_odds"]

    assert (odds["library_size"], odds["lands_in_library"], odds["on_the_play"]) == (99, 36, False)
    assert odds["critical_turn"]["turn"] == 4
    assert odds["critical_turn"]["commander_weight"] == 0.6
    assert len(odds["by_turn"]) == 10
    assert odds["at_critical_turn"] == odds["by_turn"][3]
    assert sorted(odds["by_turn"][0]["p_at_least"], key=int) == [str(k) for k in range(1, 11)]
    assert odds["by_turn"][3]["p_land_drops"] == pytest.approx(0.6213, abs=1e-3)


def test_json_options_change_the_critical_turn_and_the_draw_convention(client: TestClient) -> None:
    body = post(client, MIXED, commander_weight=0.0, on_the_play=True)

    assert body["options"] == {
        "count_mdfc_lands": True,
        "commander_weight": 0.0,
        "on_the_play": True,
    }
    assert body["land_odds"]["critical_turn"]["raw"] == 3.0
    assert body["land_odds"]["on_the_play"] is True
    assert body["land_odds"]["by_turn"][0]["cards_seen"] == 7


def test_text_endpoint_reads_the_new_options_from_the_query_string(client: TestClient) -> None:
    body = post_text(client, MIXED, "?commander_weight=1&on_the_play=true").json()

    assert body["options"]["commander_weight"] == 1.0
    assert body["options"]["on_the_play"] is True
    assert body["land_odds"]["critical_turn"]["raw"] == 4.0


@pytest.mark.parametrize("weight", [-0.1, 1.5])
def test_commander_weight_out_of_range_is_rejected(client: TestClient, weight: float) -> None:
    json_response = client.post(
        "/analyses", json={"decklist": MIXED, "options": {"commander_weight": weight}}
    )
    text_response = post_text(client, MIXED, f"?commander_weight={weight}")

    assert json_response.status_code == 422
    assert text_response.status_code == 422


def test_empty_library_returns_null_land_odds(client: TestClient) -> None:
    body = post(client, "Commander\n1 Atraxa, Praetors' Voice")

    assert body["land_odds"] is None


def test_response_includes_the_land_count_analysis(client: TestClient) -> None:
    analysis = post(client, MIXED)["land_odds"]["land_count"]

    assert analysis["turn"] == 4
    assert analysis["current_lands"] == 36
    assert analysis["current_probability"] == pytest.approx(0.6213, abs=1e-3)
    assert [point["delta"] for point in analysis["sensitivity"]] == list(range(-5, 6))
    assert [req["target"] for req in analysis["required"]] == [0.7, 0.8, 0.9]
    lands = [req["lands"] for req in analysis["required"]]
    assert lands == sorted(lands)
    assert all(req["delta"] == req["lands"] - 36 for req in analysis["required"])


def test_land_count_follows_the_play_option(client: TestClient) -> None:
    draw = post(client, MIXED)["land_odds"]["land_count"]
    play = post(client, MIXED, on_the_play=True)["land_odds"]["land_count"]

    assert play["cards_seen"] == draw["cards_seen"] - 1
    assert play["current_probability"] < draw["current_probability"]


def test_land_count_is_null_when_there_is_no_critical_turn(client: TestClient) -> None:
    body = post(
        client, "1 Island"
    )  # sem comandante e só terreno: não há custo para o turno crítico

    assert body["land_odds"]["critical_turn"] is None
    assert body["land_odds"]["land_count"] is None


CATEGORIZED = "Commander\n1 Elf Chief\nDeck\n1 Sol Ring\n1 Swords to Plowshares\n97 Forest\n"


def test_response_counts_the_deck_by_category(client: TestClient) -> None:
    categories = post(client, CATEGORIZED)["categories"]

    by_name = {c["category"]: c for c in categories["categories"]}
    assert categories["main_cards"] == 99
    assert categories["classifier_version"].startswith("rules-")
    assert [c["category"] for c in categories["categories"]][:3] == ["ramp", "card_draw", "tutor"]
    assert by_name["ramp"]["count"] == 1
    assert by_name["ramp"]["cards"] == ["Sol Ring"]
    assert by_name["ramp"]["percent"] == pytest.approx(1 / 99)
    assert by_name["removal"]["count"] == 1
    assert by_name["interaction"]["count"] == 1
    assert by_name["combo_piece"]["supported"] is False
    assert by_name["combo_piece"]["count"] == 0


def test_each_card_lists_its_categories(client: TestClient) -> None:
    cards = {c["name"]: c for c in post(client, CATEGORIZED)["cards"]}

    assert cards["Sol Ring"]["categories"] == ["ramp"]
    assert cards["Swords to Plowshares"]["categories"] == ["interaction", "removal"]
    assert cards["Forest"]["categories"] == []


def test_the_commanders_categories_are_reported_apart(client: TestClient) -> None:
    categories = post(client, CATEGORIZED)["categories"]

    assert categories["commander_categories"] == {"Elf Chief": []}
