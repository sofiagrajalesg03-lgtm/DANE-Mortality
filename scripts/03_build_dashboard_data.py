"""Paso 3: construir el archivo de datos del dashboard (dashboard/data/datos.json).

Lee data/processed/cuadro5_largo.csv.gz (paso 2) y arma un "cubo" compacto:
cada fila es [año, departamento, causa, grupo de edad, sexo, n] con índices a las listas
de `dims`. El navegador filtra y suma ese cubo, sin servidor.

  nac -> todo el país, por departamento de residencia (incluye Extranjero y Sin información)
  med -> solo Medellín: [año, causa, grupo de edad, sexo, n]

Uso: python scripts/03_build_dashboard_data.py
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
from config import FUENTE, LARGO_FILE, MEDELLIN_COD, OUT_DIR, SEXOS  # noqa: E402

MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
         "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}
ABR = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
SIN_INFO = "Sin información"


def periodo_info(anio: int, periodo: str, parcial: bool, preliminar: bool) -> dict:
    """Etiqueta legible del periodo, leída del texto del propio archivo del DANE."""
    label = str(anio)
    if parcial:
        m = re.search(r"entre el \d+ de (\w+) y el \d+ de (\w+)", periodo.lower())
        if m and m.group(1) in MESES and m.group(2) in MESES:
            label = f"{anio} ({ABR[MESES[m.group(1)] - 1]}–{ABR[MESES[m.group(2)] - 1]}"
            label += ", prelim.)" if preliminar else ")"
        else:
            label = f"{anio} (parcial)"
    elif preliminar:
        label = f"{anio} (prelim.)"
    return {"anio": anio, "label": label, "parcial": bool(parcial), "preliminar": bool(preliminar),
            "periodo": periodo}


def main() -> None:
    if not LARGO_FILE.exists():
        raise SystemExit(f"Falta {LARGO_FILE}. Corre primero scripts/02_read_cuadros.py")
    df = pd.read_csv(LARGO_FILE, dtype={"cod_mpio": str, "cod_dpto": str})
    df["nombre"] = df["nombre"].replace({"Sin Información": SIN_INFO})
    print(f"Leídas {len(df):,} filas; años: {sorted(df.anio.unique().tolist())}")

    # ---- dimensiones -------------------------------------------------------------------
    info = (df.groupby("anio")[["periodo", "parcial", "preliminar"]].first().reset_index()
            .sort_values("anio"))
    anios = [periodo_info(int(r.anio), r.periodo, r.parcial, r.preliminar) for r in info.itertuples()]
    a_idx = {a["anio"]: i for i, a in enumerate(anios)}

    edades = [g for g in df.grupo_edad.unique() if g != "Total"]
    e_idx = {g: i for i, g in enumerate(edades)}
    s_idx = {s: i for i, s in enumerate(SEXOS)}

    # Causas: el código identifica la causa; el nombre puede traer erratas en algún año
    # (en el archivo de 2026pr: "Tumo", "beningnos", "cróncas"). Usamos el nombre que
    # aparece en más años y, en empate, el del año más antiguo.
    c = df[df.causa_cod != "TOTAL"][["anio", "causa_cod", "causa"]].drop_duplicates()
    nombres_por_cod = c.groupby("causa_cod")["causa"].nunique()
    if (nombres_por_cod > 1).any():
        print(f"  [aviso] {(nombres_por_cod > 1).sum()} causas cambian de redacción entre años "
              "(erratas); se usa el nombre más frecuente")
    c = (c.assign(veces=c.groupby(["causa_cod", "causa"])["anio"].transform("count"))
          .sort_values(["causa_cod", "veces", "anio"], ascending=[True, False, True])
          .drop_duplicates("causa_cod", keep="first"))
    causas = [{"cod": r.causa_cod, "nombre": r.causa} for r in c.itertuples()]
    c_idx = {x["cod"]: i for i, x in enumerate(causas)}

    deptos = sorted(df[df.nivel == "departamento"].nombre.unique().tolist())
    dptos = deptos + ["Extranjero", SIN_INFO]
    d_idx = {n: i for i, n in enumerate(dptos)}

    # ---- cubo nacional (por departamento de residencia) -------------------------------
    base = df[(df.causa_cod != "TOTAL") & (df.grupo_edad != "Total")]
    nac = base[base.nivel.isin(["departamento", "extranjero", "otro"])]
    nac = nac.groupby(["anio", "nombre", "causa_cod", "grupo_edad", "sexo"], as_index=False)["n"].sum()
    nac_rows = [[a_idx[r.anio], d_idx[r.nombre], c_idx[r.causa_cod], e_idx[r.grupo_edad],
                 s_idx[r.sexo], int(r.n)] for r in nac.itertuples()]

    # ---- cubo Medellín ----------------------------------------------------------------
    med = base[base.cod_mpio == MEDELLIN_COD]
    med = med.groupby(["anio", "causa_cod", "grupo_edad", "sexo"], as_index=False)["n"].sum()
    med_rows = [[a_idx[r.anio], c_idx[r.causa_cod], e_idx[r.grupo_edad], s_idx[r.sexo], int(r.n)]
                for r in med.itertuples()]

    # ---- validaciones contra los totales del propio DANE ------------------------------
    print("Validación del cubo contra los bloques del DANE:")
    ok = True
    nacional = base[base.nivel == "nacional"].groupby(["anio", "causa_cod", "grupo_edad", "sexo"])["n"].sum()
    cubo = nac.groupby(["anio", "causa_cod", "grupo_edad", "sexo"])["n"].sum()
    j = pd.concat([nacional.rename("dane"), cubo.rename("cubo")], axis=1).fillna(0)
    malos = int((j.dane != j.cubo).sum())
    print(f"  Celdas año×causa×edad×sexo donde la suma de departamentos ≠ nacional: {malos} de {len(j):,}")
    ok &= malos == 0
    tot_dane = df[(df.nivel == "nacional") & (df.causa_cod == "TOTAL") & (df.grupo_edad == "Total")] \
        .groupby("anio")["n"].sum()
    tot_cubo = nac.groupby("anio")["n"].sum()
    for a in tot_dane.index:
        igual = tot_dane[a] == tot_cubo.get(a, -1)
        ok &= bool(igual)
        print(f"  {a}: total DANE {tot_dane[a]:,} vs cubo {tot_cubo.get(a, 0):,} -> {'OK' if igual else 'NO CUADRA'}")
    t_med = df[(df.cod_mpio == MEDELLIN_COD) & (df.causa_cod == "TOTAL") & (df.grupo_edad == "Total")] \
        .groupby("anio")["n"].sum()
    c_med = med.groupby("anio")["n"].sum()
    for a in t_med.index:
        igual = t_med[a] == c_med.get(a, -1)
        ok &= bool(igual)
        print(f"  Medellín {a}: total DANE {t_med[a]:,} vs cubo {c_med.get(a, 0):,} -> {'OK' if igual else 'NO CUADRA'}")
    if not ok:
        raise SystemExit("El cubo no cuadra con el DANE: no se escribe nada.")

    # ---- calidad de la asignación geográfica ------------------------------------------
    calidad = {}
    for a in anios:
        t = int(tot_dane[a["anio"]])
        ext = int(nac[(nac.anio == a["anio"]) & (nac.nombre == "Extranjero")]["n"].sum())
        sin = int(nac[(nac.anio == a["anio"]) & (nac.nombre == SIN_INFO)]["n"].sum())
        calidad[str(a["anio"])] = {"total": t, "extranjero": ext, "sin_info": sin}

    out = {
        "meta": {"fuente": FUENTE, "generado": date.today().isoformat(), "calidad": calidad,
                 "medellin_cod": MEDELLIN_COD},
        "dims": {"anios": anios, "sexos": SEXOS, "edades": edades, "causas": causas, "dptos": dptos},
        "nac": nac_rows,
        "med": med_rows,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dest = OUT_DIR / "datos.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"\nEscrito {dest} ({dest.stat().st_size / 1e6:.2f} MB): "
          f"{len(nac_rows):,} filas nacionales, {len(med_rows):,} de Medellín")


if __name__ == "__main__":
    main()
