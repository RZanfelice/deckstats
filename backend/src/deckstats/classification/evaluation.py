"""Métricas do classificador contra um conjunto de validação rotulado à mão."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from deckstats.catalog.records import CardRecord
from deckstats.classification import taxonomy as t
from deckstats.classification.classifier import classify_card


@dataclass(frozen=True, slots=True)
class CategoryScore:
    category: str
    true_positives: int
    false_positives: int
    false_negatives: int
    support: int  # quantas cartas têm a categoria no gabarito

    @property
    def precision(self) -> float:
        predicted = self.true_positives + self.false_positives
        return self.true_positives / predicted if predicted else 1.0

    @property
    def recall(self) -> float:
        actual = self.true_positives + self.false_negatives
        return self.true_positives / actual if actual else 1.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0


@dataclass(frozen=True, slots=True)
class Disagreement:
    card: str
    category: str
    kind: str  # "falso positivo" ou "falso negativo"
    excerpt: str


@dataclass(frozen=True, slots=True)
class Report:
    scores: dict[str, CategoryScore]
    disagreements: list[Disagreement]
    cards: int
    missing: list[str]

    @property
    def macro_f1(self) -> float:
        scored = [s for s in self.scores.values() if s.support]
        return sum(s.f1 for s in scored) / len(scored) if scored else 0.0


def evaluate(
    labels: Mapping[str, list[str]],
    lookup: Callable[[str], CardRecord | None],
) -> Report:
    """Compara as categorias previstas com as do gabarito (fecho de implicações nos dois lados)."""
    tp = dict.fromkeys(t.SUPPORTED, 0)
    fp = dict.fromkeys(t.SUPPORTED, 0)
    fn = dict.fromkeys(t.SUPPORTED, 0)
    support = dict.fromkeys(t.SUPPORTED, 0)
    disagreements: list[Disagreement] = []
    missing: list[str] = []
    evaluated = 0

    for name, expected_list in labels.items():
        card = lookup(name)
        if card is None:
            missing.append(name)
            continue
        evaluated += 1
        result = classify_card(card)
        expected = t.close_over_implications(set(expected_list))
        predicted = set(result.categories)
        for category in t.SUPPORTED:
            in_expected, in_predicted = category in expected, category in predicted
            support[category] += in_expected
            if in_expected and in_predicted:
                tp[category] += 1
            elif in_predicted:
                fp[category] += 1
                evidence = result.evidence.get(category)
                excerpt = evidence[0].excerpt if evidence else "(implicada por outra categoria)"
                disagreements.append(Disagreement(name, category, "falso positivo", excerpt))
            elif in_expected:
                fn[category] += 1
                disagreements.append(Disagreement(name, category, "falso negativo", ""))

    scores = {c: CategoryScore(c, tp[c], fp[c], fn[c], support[c]) for c in t.SUPPORTED}
    return Report(scores, disagreements, evaluated, missing)
