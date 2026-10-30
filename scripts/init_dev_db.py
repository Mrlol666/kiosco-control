"""Copia la base seed inmutable a instance/kiosco_dev.sqlite y asegura el carrito."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import aplicar_estructura_v03

SEED = ROOT / "data" / "seed" / "kiosco_merlo_sepa.sqlite"
DEST = ROOT / "instance" / "kiosco_dev.sqlite"


def inicializar(seed: Path, dest: Path, force: bool = False) -> int:
    if not seed.is_file():
        print(f"No se encontró la base seed: {seed}", file=sys.stderr)
        return 2

    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists() and not force:
        aplicar_estructura_v03(dest, seed)
        print(
            f"Ya existe {dest}. No se reemplazaron los datos.\n"
            "Se aseguró la estructura de v0.3."
        )
        return 0

    shutil.copyfile(seed, dest)
    aplicar_estructura_v03(dest, seed)
    print(f"Base de desarrollo lista: {dest}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Copia data/seed/kiosco_merlo_sepa.sqlite a instance/kiosco_dev.sqlite "
            "y crea las tablas del carrito si faltan."
        )
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Sobrescribe instance/kiosco_dev.sqlite si ya existe. Nunca modifica la seed.",
    )
    args = parser.parse_args(argv)
    return inicializar(SEED, DEST, force=args.force)


if __name__ == "__main__":
    raise SystemExit(main())
