"""Paso 1: explorar los archivos crudos antes de limpiar.

Uso: python scripts/01_explore.py
Lee todos los .csv / .xlsx de data/raw y muestra columnas, nulos y valores frecuentes.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
from config import RAW_DIR  # noqa: E402


def read_any(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    # Los CSV del DANE suelen venir en latin-1 y a veces con ';'
    for enc in ("utf-8", "latin-1"):
        try:
            return pd.read_csv(path, sep=None, engine="python", encoding=enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"No pude leer {path}")


def main() -> None:
    files = sorted(p for p in RAW_DIR.glob("*") if p.suffix.lower() in {".csv", ".xlsx", ".xls"})
    if not files:
        print(f"No hay archivos en {RAW_DIR}. Descarga los microdatos del DANE primero.")
        return
    for f in files:
        df = read_any(f)
        print("=" * 70)
        print(f.name, "->", df.shape[0], "filas,", df.shape[1], "columnas")
        print("\nColumnas y % de nulos:")
        print((df.isna().mean() * 100).round(1).to_string())
        print("\nPrimeras filas:")
        print(df.head(3).to_string())
        for c in df.columns[:12]:
            if df[c].nunique() <= 15:
                print(f"\nValores de {c}:")
                print(df[c].value_counts(dropna=False).head(15).to_string())


if __name__ == "__main__":
    main()
