"""Configuración compartida por todos los scripts.

Si cambias de carpeta o de año, casi todo se ajusta solo: los scripts detectan el año
y el periodo (año completo o año corrido) leyendo los propios archivos del DANE.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Entradas (tú pones aquí los .xlsx del DANE)
CUADROS_DIR = ROOT / "data" / "raw" / "cuadros"
MEDELLIN_RAW_DIR = ROOT / "data" / "raw" / "medellin"

# Intermedio (no se sube a git)
PROCESSED_DIR = ROOT / "data" / "processed"
LARGO_FILE = PROCESSED_DIR / "cuadro5_largo.csv.gz"

# Salida: lo que publica Netlify
OUT_DIR = ROOT / "dashboard" / "data"

# Municipio de interés (código DIVIPOLA de 5 dígitos)
MEDELLIN_COD = "05001"

SEXOS = ["Hombre", "Mujer", "Indeterminado"]

# Grupos de edad del Cuadro 5, en el orden en que aparecen en el .xlsx.
# (nombre, columna de inicio; cada grupo ocupa 3 columnas: hombre, mujer, indeterminado)
GRUPOS_EDAD = [
    ("Total", 6), ("Menor 1 año", 9), ("1-4 años", 12), ("5-14 años", 15),
    ("15-44 años", 18), ("45-64 años", 21), ("65-84 años", 24),
    ("85-99 años", 27), ("100 y más", 30), ("Edad desconocida", 33),
]

FUENTE = "DANE, Estadísticas Vitales (EEVV): defunciones no fetales, por lugar de residencia"
