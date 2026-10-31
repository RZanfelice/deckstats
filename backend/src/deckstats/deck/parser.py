"""Parser de listas de deck coladas como texto.

Aceita os exports comuns (MTGO, Arena, Moxfield, Archidekt):

    1 Sol Ring            1x Sol Ring           Sol Ring
    1 Sol Ring (C21) 263  1x Sol Ring (c21) 263 *F* [Ramp] ^Have,#37d67d^
    SB: 1 Atraxa, Praetors' Voice

Seções (``Commander``, ``Deck``, ``Sideboard``...) são opcionais. Sem nenhuma
seção explícita, a primeira linha em branco depois das cartas separa o deck do
sideboard (como no MTGO, que lista o comandante no sideboard).
"""

import re
from dataclasses import dataclass, field

from deckstats.catalog.normalize import normalize_name
from deckstats.deck.model import Section

MAX_QUANTITY = 999

_SECTION_ALIASES: dict[str, Section] = {
    "commander": "commander",
    "commanders": "commander",
    "comandante": "commander",
    "deck": "main",
    "main": "main",
    "maindeck": "main",
    "main deck": "main",
    "mainboard": "main",
    "sideboard": "sideboard",
    "side": "sideboard",
    "sb": "sideboard",
    "maybeboard": "maybeboard",
    "maybe": "maybeboard",
    "considering": "maybeboard",
    "companion": "companion",
}

_HEADER_COUNT = re.compile(r"\s*\(\d+\)\s*$")
_SIDEBOARD_PREFIX = re.compile(r"^SB:\s*", re.IGNORECASE)
_TAGS = re.compile(r"(\s*\[[^\]]*\])+\s*$|\s*\^[^^]*\^\s*$")
_FOIL = re.compile(r"\s*\*[A-Za-z]+\*\s*$")
_QUANTITY = re.compile(r"^(?P<qty>\d+)\s*[xX]?\s+(?P<rest>.+)$")
_PRINTING = re.compile(
    r"^(?P<name>.+?)\s+\((?P<set>[A-Za-z0-9]{2,6})\)(?:\s+(?P<number>[\w★\-]+))?$"
)


@dataclass(frozen=True, slots=True)
class ParsedLine:
    line_number: int
    quantity: int
    name: str
    section: Section
    set_code: str | None = None
    collector_number: str | None = None


@dataclass(frozen=True, slots=True)
class ParseError:
    line_number: int
    text: str
    reason: str


@dataclass(frozen=True, slots=True)
class ParsedDeck:
    lines: list[ParsedLine] = field(default_factory=list)
    errors: list[ParseError] = field(default_factory=list)
    # Sem cabeçalhos, a 1ª linha em branco separa 'main' de 'sideboard' só por convenção.
    has_headers: bool = False

    def merged(self) -> list[ParsedLine]:
        """Junta linhas repetidas do mesmo nome na mesma seção, somando as quantidades."""
        merged: dict[tuple[str, Section], ParsedLine] = {}
        for line in self.lines:
            key = (normalize_name(line.name), line.section)
            if key in merged:
                previous = merged[key]
                merged[key] = ParsedLine(
                    previous.line_number,
                    previous.quantity + line.quantity,
                    previous.name,
                    previous.section,
                    previous.set_code,
                    previous.collector_number,
                )
            else:
                merged[key] = line
        return list(merged.values())


def _section_header(text: str) -> Section | None:
    key = _HEADER_COUNT.sub("", text.strip().rstrip(":")).strip().lower()
    return _SECTION_ALIASES.get(key)


def _parse_card(text: str) -> tuple[int, str, str | None, str | None] | str:
    """Devolve (quantidade, nome, set, número) ou o motivo do erro."""
    body = _TAGS.sub("", text.strip())
    body = _FOIL.sub("", body).strip()
    quantity = 1
    match = _QUANTITY.match(body)
    if match:
        quantity = int(match.group("qty"))
        body = match.group("rest").strip()
    if quantity < 1 or quantity > MAX_QUANTITY:
        return "invalid_quantity"
    set_code = number = None
    printing = _PRINTING.match(body)
    if printing:
        body = printing.group("name").strip()
        set_code = printing.group("set").upper()
        number = printing.group("number")
    if not body:
        return "missing_name"
    return quantity, body, set_code, number


def parse_decklist(text: str) -> ParsedDeck:
    raw_lines = text.splitlines()
    has_headers = any(_section_header(line) for line in raw_lines)

    section: Section = "main"
    seen_card = False
    result = ParsedDeck(has_headers=has_headers)

    for number, raw in enumerate(raw_lines, start=1):
        line = raw.strip()
        if not line:
            if not has_headers and seen_card and section == "main":
                section = "sideboard"
            continue
        if line.startswith(("#", "//")):
            continue
        header = _section_header(line)
        if header:
            section = header
            continue

        line_section = section
        if _SIDEBOARD_PREFIX.match(line):
            line_section = "sideboard"
            line = _SIDEBOARD_PREFIX.sub("", line)

        parsed = _parse_card(line)
        if isinstance(parsed, str):
            result.errors.append(ParseError(number, raw.strip(), parsed))
            continue
        quantity, name, set_code, collector_number = parsed
        seen_card = True
        result.lines.append(
            ParsedLine(number, quantity, name, line_section, set_code, collector_number)
        )
    return result
