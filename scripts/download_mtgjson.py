"""Baixa os CSVs do MTGJSON para data/raw/mtgjson.

O MTGJSON só publica a versão mais recente neste endereço, então o script
registra a versão baixada (meta.csv) para que a ingestão saiba qual usou.

Uso:
    python scripts/download_mtgjson.py [--force]
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

URL = "https://mtgjson.com/api/v5/AllPrintingsCSVFiles.zip"
DEST = Path(__file__).resolve().parent.parent / "data" / "raw" / "mtgjson"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="baixa mesmo se já existir")
    args = parser.parse_args()

    if (DEST / "meta.csv").exists() and not args.force:
        print(f"{DEST} já existe ({(DEST / 'meta.csv').read_text().splitlines()[-1]}). Use --force.")
        return 0

    DEST.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "mtgjson.zip"
        print(f"Baixando {URL} ...")
        urllib.request.urlretrieve(URL, archive)  # noqa: S310 - URL fixa e confiável

        if DEST.exists():
            shutil.rmtree(DEST)
        DEST.mkdir(parents=True)
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(DEST)

    print(f"Pronto. Versão: {(DEST / 'meta.csv').read_text().splitlines()[-1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
