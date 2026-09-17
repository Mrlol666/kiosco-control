"""Copia la base seed inmutable a instance/kiosco_dev.sqlite."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "data" / "seed" / "kiosco_merlo_sepa.sqlite"
DEST = ROOT / "instance" / "kiosco_dev.sqlite"


def copy_seed(seed: Path, dest: Path, force: bool = False) -> int:
    if not seed.is_file():
        print(f"No se encontró la base seed: {seed}", file=sys.stderr)
        return 2

    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists() and not force:
        print(
            f"Ya existe {dest}. No se sobrescribe.\n"
            "Usá --force si querés reemplazar la base de desarrollo."
        )
        return 1

    shutil.copyfile(seed, dest)
    print(f"Base de desarrollo lista: {dest}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Copia data/seed/kiosco_merlo_sepa.sqlite a instance/kiosco_dev.sqlite."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Sobrescribe instance/kiosco_dev.sqlite si ya existe. Nunca modifica la seed.",
    )
    args = parser.parse_args(argv)
    return copy_seed(SEED, DEST, force=args.force)


if __name__ == "__main__":
    raise SystemExit(main())
