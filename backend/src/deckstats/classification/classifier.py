from collections import defaultdict
from dataclasses import dataclass, field

from deckstats.catalog.records import CardRecord
from deckstats.classification import taxonomy as t
from deckstats.classification.rules import RULES, make_context


@dataclass(frozen=True, slots=True)
class Evidence:
    """Por que a carta recebeu a categoria: qual regra, em qual face, com qual trecho."""

    category: str
    rule: str
    face: str
    excerpt: str


@dataclass(frozen=True, slots=True)
class Classification:
    oracle_id: str
    version: str
    evidence: dict[str, list[Evidence]] = field(default_factory=dict)

    @property
    def categories(self) -> frozenset[str]:
        """Categorias da carta, com as implicações (remoção => interação)."""
        return frozenset(t.close_over_implications(set(self.evidence)))

    def has(self, category: str) -> bool:
        return category in self.categories


def classify_card(card: CardRecord) -> Classification:
    """Aplica todas as regras a cada face e junta as evidências por categoria.

    Confiança é 0 ou 1: uma categoria presente em ``evidence`` foi ativada por pelo menos uma
    regra; as demais não. As categorias implicadas aparecem em ``categories``, sem evidência
    própria.
    """
    evidence: dict[str, list[Evidence]] = defaultdict(list)
    for face in card.faces:
        context = make_context(card, face)
        for category, rule_name, rule in RULES:
            excerpt = rule(context)
            if excerpt:
                evidence[category].append(
                    Evidence(category, rule_name, face.name, excerpt.strip()[:240])
                )
    return Classification(card.oracle_id, t.CLASSIFIER_VERSION, dict(evidence))
