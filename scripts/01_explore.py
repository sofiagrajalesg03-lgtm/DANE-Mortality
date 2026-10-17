"""Paso 1: revisar los anexos .xlsx del DANE antes de procesarlos.

Uso: python scripts/01_explore.py

Para cada archivo de data/raw/cuadros/ muestra el periodo que cubre, el total nacional y las
hojas que trae, y comprueba que la hoja Cuadro5 tenga las columnas donde el paso 2 las espera
(config.GRUPOS_EDAD). Si el DANE cambia el formato de un anexo, este paso lo avisa antes de que
se procese mal.
"""
import sys
from pathlib import Path

import openpyxl

sys.path.append(str(Path(__file__).resolve().parents[1]))
from config import CUADROS_DIR, GRUPOS_EDAD  # noqa: E402

FILA_GRUPOS, FILA_SEXOS = 7, 8  # índices (0-based) de las filas de encabezado del Cuadro 5


def texto(fila) -> str:
    return " ".join(str(c).strip() for c in fila if c not in (None, ""))


def revisar(path: Path) -> bool:
    print("=" * 72)
    print(path.name)
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    print(f"  Hojas ({len(wb.sheetnames)}): {', '.join(wb.sheetnames)}")
    if "Indice" in wb.sheetnames:
        for fila in list(wb["Indice"].iter_rows(values_only=True))[:6]:
            t = texto(fila)
            if t:
                print("  ·", t)
    if "Cuadro5" not in wb.sheetnames:
        print("  ERROR: no hay hoja 'Cuadro5'; el paso 2 no podrá leer este archivo.")
        return False

    filas = list(wb["Cuadro5"].iter_rows(values_only=True))
    print("  Periodo:", texto(filas[4]))
    grupos, sexos = filas[FILA_GRUPOS], filas[FILA_SEXOS]
    ok = True
    for nombre, ini in GRUPOS_EDAD:
        esperado = nombre.lower().replace(" años", "")
        real = str(grupos[ini] or "").strip().lower()
        cols = [str(sexos[ini + k] or "").strip().lower() for k in range(3)]
        bien = (esperado in real and cols[0].startswith("hombre")
                and cols[1].startswith("mujer") and cols[2].startswith("indet"))
        if not bien:
            ok = False
            print(f"  DESCUADRE en columna {ini}: se esperaba '{nombre}' y hay '{real}' / {cols}")
    print("  Columnas del Cuadro 5:", "OK, coinciden con config.GRUPOS_EDAD" if ok else "NO COINCIDEN")
    return ok


def main() -> None:
    files = sorted(CUADROS_DIR.glob("*.xlsx"))
    if not files:
        raise SystemExit(f"No hay .xlsx en {CUADROS_DIR}. Copia ahí los anexos del DANE.")
    todo_ok = all([revisar(f) for f in files])
    print("\nRESULTADO:", "todo listo para el paso 2" if todo_ok else "revisa los avisos antes de seguir")
    if not todo_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
