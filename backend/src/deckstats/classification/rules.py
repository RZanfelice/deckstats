"""Regras de texto por categoria.

Cada regra recebe o contexto de uma face e devolve o trecho que a ativou (ou
``None``). O trecho vira a explicação da classificação.

O texto é normalizado antes: minúsculas, sem texto de lembrete (entre
parênteses) e com o nome da própria carta trocado por ``this``, para separar
"sacrifique esta criatura" (não é saída de sacrifício) de "sacrifique uma
criatura" (é).
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

from deckstats.catalog.records import CardRecord, FaceRecord
from deckstats.classification import taxonomy as t

_REMINDER = re.compile(r"\([^)]*\)")
_SENTENCE = re.compile(r"[\n.]+")

_LAND_WORDS = r"(?:land|forest|island|plains|swamp|mountain)s?"
_OTHER_CARD_TYPES = re.compile(
    r"\b(?:creature|artifact|enchantment|instant|sorcery|planeswalker|permanent|battle)\b"
)
_UTILITY_TOKENS = re.compile(
    r"\b(?:treasure|clue|food|blood|map|gold|powerstone|junk|incubator|shard|role)\b"
)
_FOREIGN_CREATOR = re.compile(
    r"(?:its|that [\w ]+?'s|their) controller creates|that player creates|"
    r"(?:target|each|an) opponent creates"
)


@dataclass(frozen=True, slots=True)
class FaceContext:
    card: CardRecord
    face: FaceRecord
    text: str
    sentences: tuple[str, ...]
    types: frozenset[str]
    keywords: frozenset[str]

    @property
    def is_land(self) -> bool:
        return "Land" in self.types

    @property
    def is_spell_without_permanence(self) -> bool:
        return bool({"Instant", "Sorcery"} & self.types)


def _names(card: CardRecord, face: FaceRecord) -> list[str]:
    names = {card.name, face.name, *card.name.split(" // ")}
    for name in list(names):
        short = name.split(",")[0].strip()
        if len(short) > 3:
            names.add(short)
    return sorted(names, key=len, reverse=True)  # os mais longos primeiro


def make_context(card: CardRecord, face: FaceRecord) -> FaceContext:
    text = face.text or ""
    for name in _names(card, face):
        text = text.replace(name, "this")
    text = _REMINDER.sub(" ", text).lower()
    sentences = tuple(s.strip() for s in _SENTENCE.split(text) if s.strip())
    return FaceContext(
        card=card,
        face=face,
        text=text,
        sentences=sentences,
        types=frozenset(face.types),
        keywords=frozenset(face.keywords),
    )


Rule = Callable[[FaceContext], str | None]


def _first(ctx: FaceContext, pattern: re.Pattern[str]) -> str | None:
    for sentence in ctx.sentences:
        if pattern.search(sentence):
            return sentence
    return None


def _controlled_by_you(sentence: str, end: int) -> bool:
    """O alvo é do próprio jogador (``target creature you control`` ou ``you own``)?"""
    return bool(re.match(r"\s*(?:or [\w ]{1,20}? )?you (?:control|own)", sentence[end : end + 40]))


# --- Ramp ----------------------------------------------------------------------

_ADD_MANA = re.compile(r"\badds?\b")
# Mana paga com o sacrifício de OUTRA permanente (altares) não é rampa: custa uma carta.
_SACRIFICE_FED_MANA = re.compile(
    r"sacrifice (?!this\b|it\b)(?:a|an|another|two|three|x)\b"
    r"(?! (?:treasure|food|clue|blood|map|gold)\b)[^:.]*:[^.]*\badds?\b"
)
_FETCH_TO_BATTLEFIELD = re.compile(r"search your library for.{0,220}?onto the battlefield", re.S)
_EXTRA_LAND = re.compile(
    r"\bplay (?:an|one|two|three|x) additional lands?\b|"
    r"\bput (?:a|an|up to \w+) lands? cards? from your hand onto the battlefield"
)
_MANA_MULTIPLIER = re.compile(
    r"untap all (?:\w+ )?(?:permanents|lands) you control during each other player'?s untap step|"
    r"tap a (?:land|permanent) for mana.{0,80}(?:twice|additional)|"
    r"adds? an additional (?:one )?mana"
)


def _mana_ability(ctx: FaceContext) -> str | None:
    """Frase que adiciona mana, a menos que o custo seja sacrificar outra permanente."""
    for sentence in ctx.sentences:
        if _ADD_MANA.search(sentence) and not _SACRIFICE_FED_MANA.search(sentence):
            return sentence
    return None


def ramp_mana_permanent(ctx: FaceContext) -> str | None:
    if ctx.is_land or ctx.is_spell_without_permanence or not ctx.face.produced_mana:
        return None
    return _mana_ability(ctx)


def ramp_ritual(ctx: FaceContext) -> str | None:
    if ctx.is_land or not ctx.is_spell_without_permanence or not ctx.face.produced_mana:
        return None
    return _mana_ability(ctx)


def ramp_land_fetch(ctx: FaceContext) -> str | None:
    if ctx.is_land:
        return None
    for match in _FETCH_TO_BATTLEFIELD.finditer(ctx.text):
        span = match.group(0)
        if re.search(rf"\b{_LAND_WORDS}\b", span) and not re.search(
            r"\b(?:creature|artifact|enchantment) cards?\b", span
        ):
            return span
    return None


def ramp_extra_land_drops(ctx: FaceContext) -> str | None:
    return None if ctx.is_land else _first(ctx, _EXTRA_LAND)


def ramp_multiplier(ctx: FaceContext) -> str | None:
    return None if ctx.is_land else _first(ctx, _MANA_MULTIPLIER)


# --- Card Draw -----------------------------------------------------------------

_DRAW = re.compile(
    r"\bdraws? (?:a|an|one|two|three|four|five|six|seven|x|that many|twice that many|up to \w+)"
    r"(?: additional)? cards?\b|\bdraws? cards? equal to\b"
)
# "Opponent draws" não é compra sua; "if you would draw..." é substituição, não compra.
_OPPONENT_DRAWS = re.compile(r"(?:opponents?|target opponent) draws?|\bwould draw\b")
_DIG = re.compile(
    r"(?:look at|reveal) the top .{0,40}cards? of your library.{0,200}into your hand", re.S
)
_IMPULSE = re.compile(
    r"exile the top .{0,30}cards? of your library.{0,120}you may (?:play|cast)", re.S
)


def draw_cards(ctx: FaceContext) -> str | None:
    for sentence in ctx.sentences:
        if _DRAW.search(sentence) and not _OPPONENT_DRAWS.search(sentence):
            return sentence
    return None


def draw_dig(ctx: FaceContext) -> str | None:
    match = _DIG.search(ctx.text)
    return match.group(0) if match else None


def draw_impulse(ctx: FaceContext) -> str | None:
    match = _IMPULSE.search(ctx.text)
    return match.group(0) if match else None


def draw_investigate(ctx: FaceContext) -> str | None:
    return "investigate" if "Investigate" in ctx.keywords else None


# --- Tutor ---------------------------------------------------------------------

_SEARCH = re.compile(r"search your library for ([^,.]{0,90})")


def tutor_search(ctx: FaceContext) -> str | None:
    for sentence in ctx.sentences:
        match = _SEARCH.search(sentence)
        if not match:
            continue
        target = match.group(1)
        only_lands = re.search(rf"\b{_LAND_WORDS}\b", target) and not _OTHER_CARD_TYPES.search(
            target
        )
        if not only_lands:
            return sentence
    return None


# --- Removal -------------------------------------------------------------------

_DESTROY_TARGET = re.compile(
    r"\b(?:destroy|exile)s? (?:up to \w+ )?target (?:[\w-]+ ){0,3}"
    r"(?:creature|permanent|artifact|enchantment|planeswalker|battle|land)s?\b(?! cards?\b)"
)
_DAMAGE_TARGET = re.compile(
    r"\bdeals? (?:\w+|x) damage (?:divided as you choose )?(?:to|among) "
    r"(?:any target|up to \w+ targets?|target (?:[\w-]+ ){0,3}(?:creature|planeswalker|battle))"
)
_SHRINK = re.compile(r"target (?:[\w-]+ ){0,3}creatures? gets? -(?:\d+|x)/-(?:\d+|x)")
_LIBRARY_TUCK = re.compile(
    r"(?:the owner of target (?:[\w-]+ ){0,3}(?:permanent|creature) "
    r"shuffles it into their library)|"
    r"(?:put target (?:[\w-]+ ){0,3}(?:creature|permanent)[^.]{0,50}"
    r"(?:on the bottom of|into) (?:its owner'?s|their) library)"
)
_EDICT = re.compile(
    r"(?:target (?:opponent|player)|each opponent) sacrifices? (?:a|an|one|another) "
    r"(?:[\w-]+ )?(?:creature|permanent|artifact|enchantment|planeswalker)"
)
_FIGHT = re.compile(r"\bfights? (?:up to one )?(?:another )?target")


def removal_targeted(ctx: FaceContext) -> str | None:
    for sentence in ctx.sentences:
        match = _DESTROY_TARGET.search(sentence)
        if match and not _controlled_by_you(sentence, match.end()):
            return sentence
    return None


def removal_damage(ctx: FaceContext) -> str | None:
    return _first(ctx, _DAMAGE_TARGET)


def removal_shrink(ctx: FaceContext) -> str | None:
    return _first(ctx, _SHRINK)


def removal_tuck(ctx: FaceContext) -> str | None:
    return _first(ctx, _LIBRARY_TUCK)


def removal_edict(ctx: FaceContext) -> str | None:
    return _first(ctx, _EDICT)


def removal_fight(ctx: FaceContext) -> str | None:
    return _first(ctx, _FIGHT)


# --- Board Wipe ----------------------------------------------------------------

_DESTROY_ALL = re.compile(
    r"\b(?:destroy|exile)s? all (?:[\w-]+ ){0,4}"
    r"(?:creatures?|permanents?|artifacts?|enchantments?|planeswalkers?|lands?|battles?)"
    r"\b(?! cards?\b)"
)
_DAMAGE_EACH = re.compile(r"\bdeals? (?:\w+|x) damage to each (?:other |non\w+ )?creature")
_SHRINK_ALL = re.compile(
    r"(?:all|each) creatures? (?:[\w-]+ ){0,3}gets? -(?:\d+|x)/-(?!0\b)|"
    r"creatures (?:your opponents|target opponent) control get -(?:\d+|x)/-(?!0\b)"
)  # reduzir só o poder (-2/-0) não limpa a mesa
_BOUNCE_ALL = re.compile(
    r"return (?:all|each) (?:[\w-]+ ){0,3}(?:permanents?|creatures?)\b[^.]{0,60}hands?"
)
_SACRIFICE_ALL = re.compile(r"(?:each player|each opponent|all players) sacrifices? all")
_OVERLOADABLE = re.compile(
    r"return target (?:[\w-]+ ){0,3}(?:permanent|creature)|"
    r"(?:destroy|exile) target (?:[\w-]+ ){0,3}(?:permanent|creature|artifact|enchantment)"
)


def wipe_destroy_all(ctx: FaceContext) -> str | None:
    return _first(ctx, _DESTROY_ALL)


def wipe_damage_each(ctx: FaceContext) -> str | None:
    return _first(ctx, _DAMAGE_EACH)


def wipe_shrink_all(ctx: FaceContext) -> str | None:
    return _first(ctx, _SHRINK_ALL)


def wipe_bounce_all(ctx: FaceContext) -> str | None:
    return _first(ctx, _BOUNCE_ALL)


def wipe_sacrifice_all(ctx: FaceContext) -> str | None:
    return _first(ctx, _SACRIFICE_ALL)


def wipe_overload(ctx: FaceContext) -> str | None:
    if "Overload" not in ctx.keywords:
        return None
    return _first(ctx, _OVERLOADABLE)


# --- Counterspell --------------------------------------------------------------

_COUNTER = re.compile(r"\bcounter target\b|\bcounter (?:that|the) (?:spell|ability)\b")


def counterspell(ctx: FaceContext) -> str | None:
    return _first(ctx, _COUNTER)


# --- Protection ----------------------------------------------------------------

_PROTECTIVE = re.compile(
    r"(?P<subject>[^,.:]*?)\b(?:gains?|has|have|get)\b[^.]{0,60}?"
    r"\b(?:hexproof|indestructible|shroud|protection from)\b"
)
_BLINK = re.compile(
    r"exile target (?:[\w-]+ ){0,2}(?:creature|permanent) you control,? "
    r"then return (?:it|that card)"
)
_PHASE_OUT = re.compile(r"\bphases? out\b")
_OTHERS = (
    "creatures",
    "permanents",
    "target",
    "equipped",
    "enchanted",
    "other",
    "you",
    "each",
    "all ",
)


def protection_grant(ctx: FaceContext) -> str | None:
    for sentence in ctx.sentences:
        match = _PROTECTIVE.search(sentence)
        if not match:
            continue
        subject = match.group("subject").strip()
        if subject.startswith("this ") or not any(word in subject for word in _OTHERS):
            continue  # a carta só protege a si mesma, ou é uma lista de palavras-chave
        return sentence
    return None


def protection_blink(ctx: FaceContext) -> str | None:
    return _first(ctx, _BLINK)


def protection_phase_out(ctx: FaceContext) -> str | None:
    return _first(ctx, _PHASE_OUT)


# --- Win Condition -------------------------------------------------------------

_WIN = re.compile(r"\byou win the game\b|\b(?:target|each) (?:player|opponent) loses the game\b")
# "Each player loses half their life" é simétrico (atinge você), então não é finalizador.
_DRAIN = re.compile(
    r"(?:each opponent|target (?:opponent|player)) loses (?:x|half|that much|twice)"
    r"(?: that much)?(?: of)?(?: their)? life\b"
)
_TEAM_BONUS = re.compile(r"\+(x|\d+)/\+(x|\d+)")
_OVERRUN = re.compile(r"creatures you control (?:get|gain)\b")


def win_game(ctx: FaceContext) -> str | None:
    return _first(ctx, _WIN)


def win_drain(ctx: FaceContext) -> str | None:
    return _first(ctx, _DRAIN)


def _big_bonus(sentence: str) -> bool:
    """O poder do bônus de equipe é X ou pelo menos +2? +1/+1 ou +0/+4 não são finalizadores."""
    match = _TEAM_BONUS.search(sentence)
    if match is None:
        return False
    power = match.group(1)
    return power == "x" or int(power) >= 2


def win_overrun(ctx: FaceContext) -> str | None:
    for sentence in ctx.sentences:
        if (
            _OVERRUN.search(sentence)
            and _big_bonus(sentence)
            and re.search(r"trample|double strike", sentence)
            # um bônus permanente de equipe é lorde, não finalizador
            and "until end of turn" in sentence
        ):
            return sentence
    return None


# --- Recursion -----------------------------------------------------------------

_FROM_GRAVEYARD = re.compile(
    r"\b(?:return|put)s? (?!this )"
    r"(?:up to \w+ |another |each |all |that )?(?:target )?(?:[\w-]+ ){0,5}"
    r"cards?[^.]{0,80}\bfrom "
    r"(?:your|a|an opponent'?s|their|its owner'?s|that player'?s) graveyard\b"
    r"[^.]{0,60}(?:\bto the battlefield|\bonto the battlefield|\binto your hand|\bto your hand|"
    r"\bto its owner'?s hand|\bon top of)"
)
_REANIMATE_AURA = re.compile(r"return enchanted [\w ]*cards? to the battlefield")
_CAST_FROM_GRAVEYARD = re.compile(
    r"you may (?:cast|play)\b[^.]{0,50}\bfrom your graveyard|in your graveyard gains? flashback"
)


def recursion_return(ctx: FaceContext) -> str | None:
    match = _FROM_GRAVEYARD.search(ctx.text)
    return match.group(0) if match else _first(ctx, _REANIMATE_AURA)


def recursion_cast(ctx: FaceContext) -> str | None:
    return _first(ctx, _CAST_FROM_GRAVEYARD)


# --- Token Generator -----------------------------------------------------------

_CREATE = re.compile(r"\bcreates? (.*?)\btokens?\b")
_TOKEN_DOUBLER = re.compile(r"would create one or more tokens")
_TOKEN_KEYWORDS = frozenset({"Amass", "Populate", "Fabricate", "Afterlife"})
_TREASURE = re.compile(r"\bcreates? [^.]*\btreasure\b")


def token_create(ctx: FaceContext) -> str | None:
    for sentence in ctx.sentences:
        match = _CREATE.search(sentence)
        if not match or _FOREIGN_CREATOR.search(sentence):
            continue
        made = match.group(1)
        if "creature" in made or not _UTILITY_TOKENS.search(made):
            return sentence
    return None


def token_doubler(ctx: FaceContext) -> str | None:
    return _first(ctx, _TOKEN_DOUBLER)


def token_keyword(ctx: FaceContext) -> str | None:
    found = sorted(ctx.keywords & _TOKEN_KEYWORDS)
    return f"keyword: {', '.join(found)}" if found else None


def treasure_create(ctx: FaceContext) -> str | None:
    for sentence in ctx.sentences:
        if _TREASURE.search(sentence) and not _FOREIGN_CREATOR.search(sentence):
            return sentence
    return None


# --- Sacrifice Outlet ----------------------------------------------------------

_OUTLET = re.compile(
    r"sacrifice (?!this\b|it\b)(?:a|an|another|two|three|x|one or more) "
    r"(?!(?:treasure|food|clue|blood|map|gold)\b)(?:[\w-]+ ){0,3}[\w-]+[^:.]{0,30}:"
)


def sacrifice_outlet(ctx: FaceContext) -> str | None:
    return _first(ctx, _OUTLET)


# --- Interaction (além do que remoção, contramágica e limpa de mesa já implicam) -------

_BOUNCE = re.compile(
    r"return target (?:[\w-]+ ){0,4}"
    r"(?:creature|permanent|artifact|enchantment|planeswalker|spell)s?"
    r"[^.]{0,60}(?:to (?:its|their) owner'?s? hands?)"
)
_STEAL = re.compile(r"gain control of target|you control enchanted (?:creature|permanent)")
_LOCKDOWN = re.compile(
    r"enchanted creature can'?t attack or block|"
    r"(?<!un)\btap target (?:[\w-]+ ){0,3}(?:creature|permanent|artifact|land)\b"
)
_DISCARD = re.compile(r"(?:target (?:player|opponent)|each opponent) discards? (?:a|\w+) cards?")
_REDIRECT = re.compile(r"change the target of target")


def interaction_bounce(ctx: FaceContext) -> str | None:
    for sentence in ctx.sentences:
        match = _BOUNCE.search(sentence)
        # Aqui o "you control" cai dentro do trecho casado (antes de "to its owner's hand").
        if match and "you control" not in match.group(0):
            return sentence
    return None


def interaction_steal(ctx: FaceContext) -> str | None:
    return _first(ctx, _STEAL)


def interaction_lockdown(ctx: FaceContext) -> str | None:
    for sentence in ctx.sentences:
        match = _LOCKDOWN.search(sentence)
        if match and not _controlled_by_you(sentence, match.end()):
            return sentence
    return None


def interaction_discard(ctx: FaceContext) -> str | None:
    return _first(ctx, _DISCARD)


def interaction_redirect(ctx: FaceContext) -> str | None:
    return _first(ctx, _REDIRECT)


#: Registro: (categoria, nome da regra, função). A ordem define a ordem das evidências.
RULES: tuple[tuple[str, str, Rule], ...] = (
    (t.RAMP, "mana_permanent", ramp_mana_permanent),
    (t.RAMP, "ritual", ramp_ritual),
    (t.RAMP, "land_fetch", ramp_land_fetch),
    (t.RAMP, "extra_land_drops", ramp_extra_land_drops),
    (t.RAMP, "mana_multiplier", ramp_multiplier),
    (t.CARD_DRAW, "draw", draw_cards),
    (t.CARD_DRAW, "dig", draw_dig),
    (t.CARD_DRAW, "impulse", draw_impulse),
    (t.CARD_DRAW, "investigate", draw_investigate),
    (t.TUTOR, "search", tutor_search),
    (t.REMOVAL, "destroy_or_exile", removal_targeted),
    (t.REMOVAL, "damage", removal_damage),
    (t.REMOVAL, "shrink", removal_shrink),
    (t.REMOVAL, "tuck", removal_tuck),
    (t.REMOVAL, "edict", removal_edict),
    (t.REMOVAL, "fight", removal_fight),
    (t.BOARD_WIPE, "destroy_all", wipe_destroy_all),
    (t.BOARD_WIPE, "damage_each", wipe_damage_each),
    (t.BOARD_WIPE, "shrink_all", wipe_shrink_all),
    (t.BOARD_WIPE, "bounce_all", wipe_bounce_all),
    (t.BOARD_WIPE, "sacrifice_all", wipe_sacrifice_all),
    (t.BOARD_WIPE, "overload", wipe_overload),
    (t.COUNTERSPELL, "counter", counterspell),
    (t.PROTECTION, "grant", protection_grant),
    (t.PROTECTION, "blink", protection_blink),
    (t.PROTECTION, "phase_out", protection_phase_out),
    (t.WIN_CONDITION, "win_game", win_game),
    (t.WIN_CONDITION, "drain", win_drain),
    (t.WIN_CONDITION, "overrun", win_overrun),
    (t.RECURSION, "return", recursion_return),
    (t.RECURSION, "cast", recursion_cast),
    (t.TOKEN_GENERATOR, "create", token_create),
    (t.TOKEN_GENERATOR, "doubler", token_doubler),
    (t.TOKEN_GENERATOR, "keyword", token_keyword),
    (t.TREASURE_GENERATOR, "create", treasure_create),
    (t.SACRIFICE_OUTLET, "outlet", sacrifice_outlet),
    (t.INTERACTION, "bounce", interaction_bounce),
    (t.INTERACTION, "steal", interaction_steal),
    (t.INTERACTION, "lockdown", interaction_lockdown),
    (t.INTERACTION, "discard", interaction_discard),
    (t.INTERACTION, "redirect", interaction_redirect),
)
