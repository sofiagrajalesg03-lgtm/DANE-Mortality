"""Paso 2: limpiar y agregar. Genera los JSON que consume el dashboard.

Uso: python scripts/02_aggregate.py

Salida (dashboard/data/):
  meta.json         -> años disponibles, fuente, fecha de generación
  anual.json        -> defunciones por año y sexo
  mensual.json      -> defunciones por año y mes
  dpto.json         -> defunciones por año, departamento y sexo
  edad.json         -> defunciones por año, grupo de edad y sexo
  causa.json        -> defunciones por año y causa
"""
import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
from config import (  # noqa: E402
    CAUSA_LABELS, COLS, DPTO_LABELS, EDAD_LABELS, OUT_DIR, RAW_DIR, SEXO_LABELS,
)

sys.path.append(str(Path(__file__).resolve().parent))


def read_any(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    for enc in ("utf-8", "latin-1"):
        try:
            return pd.read_csv(path, sep=None, engine="python", encoding=enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"No pude leer {path}")


def load() -> pd.DataFrame:
    files = sorted(p for p in RAW_DIR.glob("*") if p.suffix.lower() in {".csv", ".xlsx", ".xls"})
    if not files:
        raise SystemExit(f"No hay archivos en {RAW_DIR}")
    frames = []
    for f in files:
        df = read_any(f)
        # Renombra a los nombres internos; ignora las claves con None o ausentes.
        rename = {v: k for k, v in COLS.items() if v and v in df.columns}
        missing = [k for k, v in COLS.items() if v and v not in df.columns]
        if missing:
            print(f"[aviso] {f.name}: faltan columnas para {missing}. Revisa COLS en config.py")
        frames.append(df.rename(columns=rename)[list(rename.values())])
    return pd.concat(frames, ignore_index=True)


def clean(df: pd.DataFrame) -> pd.DataFrame:
    n0 = len(df)
    for c in ("anio", "mes", "dpto", "sexo"):
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["anio"]).copy()
    df["anio"] = df["anio"].astype(int)

    # DECISIÓN DE ANÁLISIS: aquí decides qué haces con los "sin información".
    # Por defecto los conservamos con la etiqueta "Sin información" para no esconderlos.
    df["sexo_l"] = df["sexo"].map(SEXO_LABELS).fillna("Sin información")
    df["dpto_l"] = df["dpto"].map(DPTO_LABELS).fillna("Sin información")
    if "grupo_edad" in df:
        df["edad_l"] = df["grupo_edad"].map(EDAD_LABELS).fillna(df["grupo_edad"].astype(str))
    if "causa" in df:
        df["causa_l"] = df["causa"].map(CAUSA_LABELS).fillna(df["causa"].astype(str))
    print(f"Filas: {n0} -> {len(df)} tras limpieza")
    return df


def dump(name: str, obj) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / name).write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    print("escrito", name)


def agg(df: pd.DataFrame, by: list[str]) -> list[dict]:
    out = df.groupby(by, dropna=False).size().reset_index(name="n")
    return out.to_dict(orient="records")


def main() -> None:
    df = clean(load())

    dump("anual.json", agg(df, ["anio", "sexo_l"]))
    if "mes" in df:
        dump("mensual.json", agg(df.dropna(subset=["mes"]).assign(mes=lambda d: d.mes.astype(int)), ["anio", "mes"]))
    dump("dpto.json", agg(df, ["anio", "dpto_l", "sexo_l"]))
    if "edad_l" in df:
        dump("edad.json", agg(df, ["anio", "edad_l", "sexo_l"]))
    if "causa_l" in df:
        dump("causa.json", agg(df, ["anio", "causa_l"]))

    dump("meta.json", {
        "anios": sorted(df["anio"].unique().tolist()),
        "total": int(len(df)),
        "fuente": "DANE, Estadísticas Vitales (EEVV), defunciones no fetales",
        "generado": date.today().isoformat(),
    })


if __name__ == "__main__":
    main()
