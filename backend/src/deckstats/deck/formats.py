"""Regras de formato. Só Commander por enquanto, atrás de uma interface.

As regras apontam problemas (``Issue``) e nunca bloqueiam a análise.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from deckstats.catalog.records import CardRecord
from deckstats.deck.model import Deck

Severity = Literal["error", "warning", "info"]

_ANY_NUMBER_OF_COPIES = "any number of cards named"


@dataclass(frozen=True, slots=True)
class Issue:
    """Problema encontrado. ``code`` e ``details`` são dados; a UI traduz para texto."""

    code: str
    severity: Severity
    cards: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


class FormatRules(Protocol):
    name: str

    def validate(self, deck: Deck) -> list[Issue]: ...


def _keywords(card: CardRecord) -> set[str]:
    """Palavras-chave em minúsculas: o MTGJSON grafa "Choose a background" e "Partner with"."""
    return {keyword.lower() for face in card.faces for keyword in face.keywords}


def _text(card: CardRecord) -> str:
    return " ".join(face.text or "" for face in card.faces)


def _is_basic_land(card: CardRecord) -> bool:
    return "Basic" in card.faces[0].supertypes


def _allows_any_number(card: CardRecord) -> bool:
    return _ANY_NUMBER_OF_COPIES in _text(card).lower()


def is_background(card: CardRecord) -> bool:
    return any("Background" in face.subtypes for face in card.faces)


def can_lead(card: CardRecord) -> bool:
    """Pode ser comandante: criatura/planeswalker com a habilidade, ou um Background.

    O MTGJSON não marca Backgrounds como comandantes (eles só valem ao lado de quem tem
    "Choose a Background"), então a regra de par é que os valida de fato.
    """
    return card.can_be_commander or is_background(card)


def _can_pair(first: CardRecord, second: CardRecord) -> bool:
    """Dois comandantes são compatíveis (Partner, Partner with, Background...)."""
    for a, b in ((first, second), (second, first)):
        a_keys, b_keys = _keywords(a), _keywords(b)
        if "partner" in a_keys and "partner" in b_keys:
            return True
        if "friends forever" in a_keys and "friends forever" in b_keys:
            return True
        if "partner with" in a_keys and b.faces[0].name.lower() in _text(a).lower():
            return True
        if "choose a background" in a_keys and is_background(b):
            return True
        if "doctor's companion" in a_keys and any("Time Lord" in f.subtypes for f in b.faces):
            return True
    return False


class CommanderRules:
    name = "commander"
    deck_size = 100
    max_commanders = 2

    def validate(self, deck: Deck) -> list[Issue]:
        issues: list[Issue] = []
        issues += self._commander_issues(deck)
        issues += self._size_issues(deck)
        issues += self._singleton_issues(deck)
        issues += self._color_identity_issues(deck)
        issues += self._legality_issues(deck)
        return issues

    def _commander_issues(self, deck: Deck) -> list[Issue]:
        commanders = deck.commanders
        if not commanders:
            return [Issue("commander_missing", "warning")]
        issues: list[Issue] = []
        if sum(entry.quantity for entry in commanders) > self.max_commanders:
            issues.append(
                Issue("too_many_commanders", "warning", [e.card.name for e in commanders])
            )
        alone = len(commanders) == 1 and commanders[0].quantity == 1
        ineligible = [
            e.card.name
            for e in commanders
            if not (e.card.can_be_commander or (is_background(e.card) and not alone))
        ]
        if ineligible:
            issues.append(Issue("commander_not_eligible", "warning", ineligible))
        if len(commanders) == self.max_commanders and not _can_pair(
            commanders[0].card, commanders[1].card
        ):
            issues.append(
                Issue("commander_pair_invalid", "warning", [e.card.name for e in commanders])
            )
        return issues

    def _size_issues(self, deck: Deck) -> list[Issue]:
        if deck.played_count == self.deck_size:
            return []
        return [
            Issue(
                "deck_size",
                "warning",
                details={"expected": self.deck_size, "actual": deck.played_count},
            )
        ]

    def _singleton_issues(self, deck: Deck) -> list[Issue]:
        copies: dict[str, int] = defaultdict(int)
        cards: dict[str, CardRecord] = {}
        for entry in deck.played:
            copies[entry.card.oracle_id] += entry.quantity
            cards[entry.card.oracle_id] = entry.card
        repeated = [
            card.name
            for oracle_id, card in cards.items()
            if copies[oracle_id] > 1 and not _is_basic_land(card) and not _allows_any_number(card)
        ]
        return [Issue("singleton_violation", "warning", sorted(repeated))] if repeated else []

    def _color_identity_issues(self, deck: Deck) -> list[Issue]:
        if not deck.commanders:
            return []
        allowed = {color for e in deck.commanders for color in e.card.color_identity}
        outside = sorted(
            {
                entry.card.name
                for entry in deck.main
                if not set(entry.card.color_identity) <= allowed
            }
        )
        if not outside:
            return []
        return [Issue("color_identity_violation", "warning", outside, {"allowed": sorted(allowed)})]

    def _legality_issues(self, deck: Deck) -> list[Issue]:
        banned = sorted({e.card.name for e in deck.played if e.card.commander_legality == "banned"})
        illegal = sorted(
            {e.card.name for e in deck.played if e.card.commander_legality == "not_legal"}
        )
        issues: list[Issue] = []
        if banned:
            issues.append(Issue("banned_cards", "warning", banned))
        if illegal:
            issues.append(Issue("not_legal_cards", "warning", illegal))
        return issues
