import pytest

from deckstats.catalog.normalize import normalize_name


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Sol Ring", "sol ring"),
        ("  Sol   Ring ", "sol ring"),
        ("Lim-Dûl's Vault", "lim-dul's vault"),
        ("Lim-Dul’s Vault", "lim-dul's vault"),
        ("Æther Vial", "aether vial"),
        ("Fire // Ice", "fire // ice"),
        ("Fire/Ice", "fire // ice"),
        ("Fire /// Ice", "fire // ice"),
        ("Fire//Ice", "fire // ice"),
        ("Jötun Grunt", "jotun grunt"),
    ],
)
def test_normalize_name(raw: str, expected: str) -> None:
    assert normalize_name(raw) == expected


def test_equivalent_spellings_share_a_key() -> None:
    assert normalize_name("Fire / Ice") == normalize_name("fire // ice")
