"""Paso 2: leer el Cuadro 5 de los anexos del DANE y pasarlo a formato largo.

Cuadro 5 = defunciones por grupo de edad y sexo, según departamento / municipio de
RESIDENCIA y grupo de causas (lista 6/67 CIE-10 OPS). Es una tabla ancha, no microdatos.

Uso:
  python scripts/02_read_cuadros.py                 # lee data/raw/cuadros/*.xlsx
  python scripts/02_read_cuadros.py a.xlsx b.xlsx   # o archivos concretos

Salida: data/processed/cuadro5_largo.csv.gz con columnas
  anio, preliminar, parcial, periodo, nivel, cod_dpto, cod_mpio, nombre,
  causa_cod, causa, grupo_edad, sexo, n
(solo filas con n > 0: el 85 % de la tabla original son ceros)

Cosas que descubrimos al validar (están documentadas en el README):
  * En los archivos de 2025 y 2026pr, la fila de total de cada departamento trae en la
    columna de código de municipio el valor 03000 (el nacional) en vez de XX000. En 2024
    viene bien. Por eso identificamos cada bloque por el NOMBRE y no por el código.
  * Hay bloques de "Extranjero" (con un sub-bloque por país) y de "Sin información".
  * Un archivo "año corrido" (2026pr) cubre solo parte del año: columna `parcial`.
"""
import re
import sys
from pathlib import Path

import openpyxl
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
from config import CUADROS_DIR, GRUPOS_EDAD, LARGO_FILE, SEXOS  # noqa: E402

# Posición de las columnas en el Cuadro 5 (idéntica en 2024, 2025 y 2026pr; verificado).
C_DPTO, C_MPIO, C_NOM_DPTO, C_NOM_MPIO, C_CAUSA = 0, 1, 2, 3, 4
CAUSA_RE = re.compile(r"^\s*(\d{3})\s+(.*)$")
DPTO_RE = re.compile(r"^\s*(\d{2})\s+(.*)$")
MPIO_RE = re.compile(r"^\s*(\d{5})\s+(.*)$")
PAIS_RE = re.compile(r"^\s*(\d{3})\s+(.*)$")


def to_int(v) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def txt(v) -> str:
    return str(v).strip() if v is not None else ""


def detect_year(periodo: str, path: Path) -> int:
    """El año sale del título de la hoja; si no está, del nombre del archivo (último 20xx)."""
    m = re.search(r"(20\d{2})", periodo)
    if m:
        return int(m.group(1))
    found = re.findall(r"(20\d{2})", path.name)
    if not found:
        raise ValueError(f"No encuentro el año en {path.name}")
    return int(found[-1])


def read_file(path: Path) -> tuple[pd.DataFrame, int]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    if "Cuadro5" not in wb.sheetnames:
        raise ValueError(f"{path.name} no tiene hoja 'Cuadro5'. Hojas: {wb.sheetnames}")
    rows = list(wb["Cuadro5"].iter_rows(values_only=True))
    # Fila 5 (índice 4): "Año 2024" o "Año corrido 2026 preliminar - (...)"
    periodo = " ".join(str(c) for c in rows[4] if c)
    anio = detect_year(periodo, path)
    parcial = "corrido" in periodo.lower()
    preliminar = "preliminar" in periodo.lower() or path.stem.lower().endswith("pr")

    cur = None  # bloque actual: (nivel, cod_dpto, cod_mpio, nombre)
    sin_bloque = 0
    recs = []
    for r in rows[9:]:  # los datos empiezan en la fila 10
        label = txt(r[C_CAUSA])
        cm = CAUSA_RE.match(label)
        es_total = (not cm) and label.lower().startswith("total")
        if not cm and not es_total:
            continue  # notas, pies de página, filas vacías

        if es_total:
            c2, c3 = txt(r[C_NOM_DPTO]), txt(r[C_NOM_MPIO])
            if c2.lower().startswith("total nacional"):
                cur = ("nacional", "03", "03000", "Total Nacional")
            elif DPTO_RE.match(c2):
                d = DPTO_RE.match(c2)
                cur = ("departamento", d.group(1), d.group(1) + "000", d.group(2).strip())
            elif c2.lower().startswith("extranjero"):
                # El código de municipio cambia entre años (75000 en 2024, 99773 en 2026).
                cur = ("extranjero", "75", "75000", "Extranjero")
            elif c2:
                cur = ("otro", txt(r[C_DPTO]), "OTRO_" + c2[:20], c2)  # p. ej. "Sin Información"
            elif MPIO_RE.match(c3):
                mm = MPIO_RE.match(c3)
                cur = ("municipio", mm.group(1)[:2], mm.group(1), mm.group(2).strip())
            elif txt(r[C_DPTO]) == "75" and PAIS_RE.match(c3):
                pm = PAIS_RE.match(c3)  # país de residencia, dentro de "Extranjero"
                cur = ("pais", "75", "75" + pm.group(1), pm.group(2).strip())
            else:
                sin_bloque += 1
                cur = None
                continue
            causa_cod, causa = "TOTAL", "Total"
        else:
            if cur is None:
                sin_bloque += 1
                continue
            causa_cod, causa = cm.group(1), cm.group(2).strip()

        nivel, cdpto, cmpio, nombre = cur
        for grupo, start in GRUPOS_EDAD:
            for k, sexo in enumerate(SEXOS):
                n = to_int(r[start + k])
                if n:  # los ceros no se guardan
                    recs.append((anio, preliminar, parcial, periodo, nivel, cdpto, cmpio, nombre,
                                 causa_cod, causa, grupo, sexo, n))

    df = pd.DataFrame(recs, columns=[
        "anio", "preliminar", "parcial", "periodo", "nivel", "cod_dpto", "cod_mpio", "nombre",
        "causa_cod", "causa", "grupo_edad", "sexo", "n",
    ])
    return df, sin_bloque


def validate(df: pd.DataFrame, sin_bloque: int) -> bool:
    """Chequeos de coherencia. Si algo no cuadra, hay que entenderlo antes de usar los datos."""
    ok = True
    tot = df[(df.causa_cod == "TOTAL") & (df.grupo_edad == "Total")]
    nac = tot[tot.nivel == "nacional"]["n"].sum()
    print(f"  Total nacional (suma sexos): {nac:,}")

    def check(nombre, a, b):
        nonlocal ok
        good = a == b
        ok &= good
        print(f"  {nombre}: {a:,} vs {b:,} -> {'OK' if good else 'NO CUADRA'}")

    def s(nv):
        return tot[tot.nivel == nv]["n"].sum()

    por_edad = df[(df.nivel == "nacional") & (df.causa_cod == "TOTAL") & (df.grupo_edad != "Total")]["n"].sum()
    check("Grupos de edad vs total nacional", por_edad, nac)
    check("Departamentos + extranjero + sin información vs nacional",
          s("departamento") + s("extranjero") + s("otro"), nac)
    check("Municipios + países + sin información vs nacional",
          s("municipio") + s("pais") + s("otro"), nac)

    # En cada bloque, las causas deben sumar el total del bloque.
    causas = df[(df.grupo_edad == "Total") & (df.causa_cod != "TOTAL")].groupby(["nivel", "cod_mpio"])["n"].sum()
    totales = tot.groupby(["nivel", "cod_mpio"])["n"].sum()
    j = pd.concat([totales.rename("t"), causas.rename("c")], axis=1).fillna(0)
    malos = int((j.t != j.c).sum())
    print(f"  Bloques donde las causas no suman el total: {malos} de {len(j)} -> {'OK' if malos == 0 else 'REVISAR'}")
    ok &= malos == 0
    print(f"  Filas sin bloque reconocible: {sin_bloque}")
    ok &= sin_bloque == 0
    return bool(ok)


def main() -> None:
    args = [Path(a) for a in sys.argv[1:]]
    files = args or sorted(CUADROS_DIR.glob("*.xlsx"))
    if not files:
        raise SystemExit(f"No hay .xlsx en {CUADROS_DIR}. Copia ahí los anexos del DANE.")
    frames, todo_ok = [], True
    for f in files:
        print(f"== {f.name} (leyendo, tarda ~30 s por archivo)")
        df, sin_bloque = read_file(f)
        etiqueta = "año corrido" if df.parcial.iloc[0] else "año completo"
        print(f"  Año {df.anio.iloc[0]} · {etiqueta}")
        todo_ok &= validate(df, sin_bloque)
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    anios = out.groupby("anio").size()
    if (anios.index.duplicated()).any():
        raise SystemExit("Dos archivos con el mismo año. Deja uno solo por año.")
    LARGO_FILE.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(LARGO_FILE, index=False, encoding="utf-8")
    print(f"\nEscrito {LARGO_FILE} ({len(out):,} filas, {LARGO_FILE.stat().st_size / 1e6:.1f} MB)")
    print("VALIDACIÓN:", "todo cuadra" if todo_ok else "hay chequeos que NO cuadran, no uses los datos aún")
    if not todo_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
