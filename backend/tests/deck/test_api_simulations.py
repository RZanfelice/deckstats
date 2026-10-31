from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from deckstats.api.deps import get_card_repository
from deckstats.catalog.repository import CardRepository, SqlCardRepository
from deckstats.main import create_app

DECK = "Commander\n1 Elf Chief\n\nDeck\n99 Forest\n"
FAST = {"iterations": 200}


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    app = create_app()

    def override() -> Iterator[CardRepository]:
        with Session(engine) as session:
            yield SqlCardRepository(session)

    app.dependency_overrides[get_card_repository] = override
    yield TestClient(app)


def post(client: TestClient, decklist: str = DECK, **options: Any) -> dict[str, Any]:
    response = client.post(
        "/simulations", json={"decklist": decklist, "options": {**FAST, **options}}
    )
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def post_text(client: TestClient, text: str = DECK, query: str = "") -> Any:
    separator = "&" if "?" in query else "?"
    return client.post(
        f"/simulations/text{query}{separator}iterations=200",
        content=text.encode("utf-8"),
        headers={"content-type": "text/plain; charset=utf-8"},
    )


def test_response_shape(client: TestClient) -> None:
    body = post(client)

    assert body["format"] == "commander"
    assert body["commanders"] == ["Elf Chief"]
    assert body["commander_inferred"] is False
    assert body["issues"] == []
    assert (body["library_size"], body["lands_in_library"]) == (99, 99)
    assert body["iterations"] == 200
    assert body["opening_hand"]["keepable"]["n"] == 200
    assert sorted(body["opening_hand"]["lands"], key=int) == [str(k) for k in range(8)]
    assert sorted(body["land_drops"], key=int) == [str(t) for t in range(1, 11)]
    assert body["mulligans"]["mean_final_hand_size"] > 0
    assert body["mana"]["plan_turn"] == 2


def test_a_deck_of_only_lands_is_never_keepable_but_always_casts_the_commander(
    client: TestClient,
) -> None:
    body = post(client, apply_mulligan=False)

    commander = body["mana"]["costs"][0]
    assert commander["source"] == "commander"
    assert commander["cost"] == "{1}{G}"
    assert commander["on_curve_turn"] == 2
    assert commander["by_turn"]["1"]["p"] == 0.0
    assert commander["by_turn"]["2"]["p"] == 1.0
    assert body["opening_hand"]["keepable"]["p"] == 0.0  # sem nenhuma magia na mão
    assert body["mulligans"] is None


def test_estimates_carry_confidence_intervals(client: TestClient) -> None:
    estimate = post(client)["land_drops"]["3"]

    assert 0.0 <= estimate["ci_low"] <= estimate["p"] <= estimate["ci_high"] <= 1.0
    assert estimate["n"] == 200


def test_custom_costs_are_evaluated(client: TestClient) -> None:
    body = post(client, costs=["{2}{G}{G}"])

    custom = next(c for c in body["mana"]["costs"] if c["source"] == "custom")
    assert custom["cost"] == "{2}{G}{G}"
    assert custom["mana_value"] == 4
    assert custom["by_turn"]["3"]["p"] == 0.0
    assert custom["by_turn"]["4"]["p"] == 1.0


def test_same_seed_gives_identical_responses_and_other_seeds_differ(client: TestClient) -> None:
    mixed = "Commander\n1 Elf Chief\nDeck\n36 Forest\n63 Cultivate\n"

    first = post(client, mixed, seed=7)
    again = post(client, mixed, seed=7)
    other = post(client, mixed, seed=8)

    assert first == again
    assert first["land_drops"] != other["land_drops"]


def test_options_are_echoed(client: TestClient) -> None:
    body = post(client, on_the_play=True, keep_min_lands=3, count_mdfc_lands=False)

    assert body["options"]["on_the_play"] is True
    assert body["options"]["keep_min_lands"] == 3
    assert body["options"]["count_mdfc_lands"] is False


def test_unresolved_cards_are_reported_as_issues_and_do_not_break_the_run(
    client: TestClient,
) -> None:
    body = post(client, DECK + "1 Solring\n")

    assert body["issues"][0]["code"] == "cards_not_found"
    assert body["library_size"] == 99


def test_commander_is_inferred_from_the_list(client: TestClient) -> None:
    body = post(client, "99 Forest\n\n1 Elf Chief\n")

    assert body["commander_inferred"] is True
    assert body["commanders"] == ["Elf Chief"]


def test_a_list_with_no_recognized_cards_is_rejected(client: TestClient) -> None:
    response = client.post("/simulations", json={"decklist": "1 Nothing Real"})

    assert response.status_code == 422


@pytest.mark.parametrize(
    "options",
    [
        {"iterations": 99},
        {"iterations": 30_001},
        {"seed": -1},
        {"max_mulligans": 7},
        {"keep_min_lands": 5, "keep_max_lands": 2},
        {"costs": ["not a cost"]},
        {"costs": ["{U}"] * 11},
    ],
)
def test_invalid_options_are_rejected(client: TestClient, options: dict[str, Any]) -> None:
    response = client.post("/simulations", json={"decklist": DECK, "options": options})

    assert response.status_code == 422


def test_text_endpoint_accepts_the_list_pasted_as_is(client: TestClient) -> None:
    response = post_text(client)

    assert response.status_code == 200
    assert response.json()["commanders"] == ["Elf Chief"]


def test_text_endpoint_matches_the_json_endpoint(client: TestClient) -> None:
    assert post_text(client, query="?seed=3").json() == post(client, seed=3)


def test_text_endpoint_reads_options_and_repeated_costs_from_the_query(client: TestClient) -> None:
    body = post_text(client, query="?on_the_play=true&costs={2}{G}&costs={3}{G}{G}").json()

    assert body["options"]["on_the_play"] is True
    custom = [c["cost"] for c in body["mana"]["costs"] if c["source"] == "custom"]
    assert custom == ["{2}{G}", "{3}{G}{G}"]


def test_text_endpoint_rejects_an_inverted_keep_range(client: TestClient) -> None:
    response = post_text(client, query="?keep_min_lands=6&keep_max_lands=3")

    assert response.status_code == 422


def test_text_endpoint_rejects_out_of_range_iterations(client: TestClient) -> None:
    response = client.post(
        "/simulations/text?iterations=5",
        content=b"1 Forest",
        headers={"content-type": "text/plain"},
    )

    assert response.status_code == 422


def test_openapi_documents_both_endpoints(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()

    assert "/simulations" in schema["paths"]
    content = schema["paths"]["/simulations/text"]["post"]["requestBody"]["content"]
    assert list(content) == ["text/plain"]
