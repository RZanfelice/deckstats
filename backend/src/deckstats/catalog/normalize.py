import re
import unicodedata

_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "ʼ": "'", "`": "'", "´": "'"})
_FACE_SEPARATOR = re.compile(r"\s*/{1,3}\s*")
_SPACES = re.compile(r"\s+")


def normalize_name(name: str) -> str:
    """Forma comparável de um nome de carta.

    Minúsculas, sem acentos, apóstrofos unificados e qualquer separador de
    faces (``/``, ``//``, ``///``) vira `` // ``. Dois nomes que um jogador
    consideraria iguais produzem a mesma chave.
    """
    text = unicodedata.normalize("NFKD", name.translate(_APOSTROPHES))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold().replace("æ", "ae")
    text = _FACE_SEPARATOR.sub(" // ", text)
    return _SPACES.sub(" ", text).strip()
