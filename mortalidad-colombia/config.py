"""Configuración del proyecto.

IMPORTANTE: los nombres de columna de los microdatos del DANE cambian entre años.
Corre scripts/01_explore.py, mira los nombres reales y ajusta COLS.
Las claves de la izquierda son los nombres internos que usa el resto del código;
los valores son los nombres de columna en TU archivo (pon None si no existe).
"""
from pathlib import Path

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "dashboard" / "data"

COLS = {
    "anio": "ANO",             # año de la defunción
    "mes": "MES",              # mes
    "dpto": "COD_DPTO",        # código de departamento (ocurrencia o residencia)
    "sexo": "SEXO",            # códigos DANE: 1 hombre, 2 mujer, 3 indeterminado
    "grupo_edad": "GRU_ED1",   # grupo quinquenal de edad
    "causa": "CAUSA_667",      # causa agrupada lista 6/67 (o la que tengas)
}

# Etiquetas legibles. Verifica los códigos contra el diccionario de variables del DANE.
SEXO_LABELS = {1: "Hombre", 2: "Mujer", 3: "Indeterminado"}

# Códigos DIVIPOLA de departamentos (2 dígitos).
DPTO_LABELS = {
    5: "Antioquia", 8: "Atlántico", 11: "Bogotá D.C.", 13: "Bolívar", 15: "Boyacá",
    17: "Caldas", 18: "Caquetá", 19: "Cauca", 20: "Cesar", 23: "Córdoba",
    25: "Cundinamarca", 27: "Chocó", 41: "Huila", 44: "La Guajira", 47: "Magdalena",
    50: "Meta", 52: "Nariño", 54: "Norte de Santander", 63: "Quindío", 66: "Risaralda",
    68: "Santander", 70: "Sucre", 73: "Tolima", 76: "Valle del Cauca", 81: "Arauca",
    85: "Casanare", 86: "Putumayo", 88: "San Andrés", 91: "Amazonas", 94: "Guainía",
    95: "Guaviare", 97: "Vaupés", 99: "Vichada",
}

# Opcional: diccionario código de causa -> nombre (rellénalo desde la lista 6/67 del DANE).
CAUSA_LABELS = {}

# Opcional: etiquetas de grupo de edad (rellénalas según el diccionario del DANE).
EDAD_LABELS = {}
