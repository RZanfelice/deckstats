"""Taxonomia fechada e versionada das categorias de carta.

Definições escritas em docs/F4_CLASSIFICATION_SPEC.md. As categorias não são
exclusivas: uma carta pode ter várias (multi-label).
"""

CLASSIFIER_VERSION = "rules-1.0.0"

RAMP = "ramp"
CARD_DRAW = "card_draw"
TUTOR = "tutor"
INTERACTION = "interaction"
PROTECTION = "protection"
REMOVAL = "removal"
BOARD_WIPE = "board_wipe"
COUNTERSPELL = "counterspell"
COMBO_PIECE = "combo_piece"
WIN_CONDITION = "win_condition"
RECURSION = "recursion"
TOKEN_GENERATOR = "token_generator"
SACRIFICE_OUTLET = "sacrifice_outlet"
TREASURE_GENERATOR = "treasure_generator"

#: Todas as categorias da spec, na ordem em que aparecem nos relatórios.
CATEGORIES: tuple[str, ...] = (
    RAMP,
    CARD_DRAW,
    TUTOR,
    INTERACTION,
    PROTECTION,
    REMOVAL,
    BOARD_WIPE,
    COUNTERSPELL,
    COMBO_PIECE,
    WIN_CONDITION,
    RECURSION,
    TOKEN_GENERATOR,
    SACRIFICE_OUTLET,
    TREASURE_GENERATOR,
)

#: Categorias que as regras de texto não conseguem decidir. Combo Piece depende de uma
#: base externa de combos (por exemplo, o Commander Spellbook).
UNSUPPORTED: frozenset[str] = frozenset({COMBO_PIECE})

#: Quem tem a chave também tem o valor. Interação é o conjunto amplo: toda remoção,
#: contramágica e limpa de mesa é interação, além de devolver à mão, roubar, imobilizar...
IMPLIES: dict[str, str] = {
    REMOVAL: INTERACTION,
    COUNTERSPELL: INTERACTION,
    BOARD_WIPE: INTERACTION,
}

SUPPORTED: tuple[str, ...] = tuple(c for c in CATEGORIES if c not in UNSUPPORTED)


def close_over_implications(categories: set[str]) -> set[str]:
    """Acrescenta as categorias implicadas (remoção => interação)."""
    result = set(categories)
    result.update(IMPLIES[c] for c in categories if c in IMPLIES)
    return result
