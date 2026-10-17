"""Paso 4 (opcional): población y densidad de Medellín por comuna y corregimiento.

Fuente: Alcaldía de Medellín, capa "Población - Proyección (2018-2030) por comuna y
corregimiento" (base: Censo 2018; proyecciones DANE–Municipio; corte 30 de junio de cada año).

Uso:
  python scripts/04_medellin_density.py                 # descarga (si no existe) y procesa
  python scripts/04_medellin_density.py --refresh       # vuelve a descargar
  python scripts/04_medellin_density.py --input a.geojson   # usa un GeoJSON que ya tengas

Si la descarga falla (red, firewall), abre la URL que imprime el script en tu navegador,
guarda el resultado como data/raw/medellin/poblacion.geojson y vuelve a correrlo.

Salida: dashboard/data/medellin_densidad.geojson
  propiedades por polígono: nombre, tipo, area_km2, pob_<año> (2018-2030)
  La densidad (hab/km²) = pob_<año> / area_km2 se calcula en el navegador.

El área se calcula desde la geometría (área esférica equivalente, error < 0.5 %) y se
contrasta con el campo st_area(shape) del servidor, para no depender de su unidad.
"""
import argparse
import json
import math
import sys
import urllib.request
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
from config import MEDELLIN_RAW_DIR, OUT_DIR  # noqa: E402

URL = (
    "https://www.medellin.gov.co/servidormapas/rest/services/mapas_nacionales/"
    "VC_Distribucion_Poblacional/MapServer/1/query"
    "?where=1%3D1&outFields=*&outSR=4326&f=geojson"
)
RAW_FILE = MEDELLIN_RAW_DIR / "poblacion.geojson"
OUT_FILE = OUT_DIR / "medellin_densidad.geojson"
YEARS = range(2018, 2031)
R = 6371008.8  # radio medio de la Tierra (m)

# Los 5 corregimientos de Medellín (zona rural). Se usan solo para etiquetar el tipo;
# el script imprime la clasificación para que la verifiques.
CORREGIMIENTOS = ("palmitas", "san cristóbal", "san cristobal", "altavista", "prado",
                  "santa elena", "corregimiento")


def download() -> Path:
    MEDELLIN_RAW_DIR.mkdir(parents=True, exist_ok=True)
    print("Descargando", URL)
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 (mortalidad-colombia)"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            RAW_FILE.write_bytes(r.read())
    except Exception as e:  # noqa: BLE001
        raise SystemExit(
            f"No pude descargar la capa ({e}).\n"
            f"Ábrela en tu navegador:\n  {URL}\n"
            f"guarda el resultado como {RAW_FILE} y vuelve a correr este script."
        )
    return RAW_FILE


def ring_area(ring: list) -> float:
    """Área (m²) de un anillo [lon, lat] sobre la esfera de área equivalente."""
    total = 0.0
    for (lon1, lat1, *_), (lon2, lat2, *_) in zip(ring, ring[1:]):
        l1, f1, l2, f2 = map(math.radians, (lon1, lat1, lon2, lat2))
        total += (l2 - l1) * (2 + math.sin(f1) + math.sin(f2))
    return abs(total) * R * R / 2


def geom_area(geom: dict) -> float:
    if geom["type"] == "Polygon":
        polys = [geom["coordinates"]]
    elif geom["type"] == "MultiPolygon":
        polys = geom["coordinates"]
    else:
        raise ValueError(f"Geometría no soportada: {geom['type']}")
    return sum(ring_area(p[0]) - sum(ring_area(h) for h in p[1:]) for p in polys)


def round_coords(c, nd=5):
    return round(c, nd) if isinstance(c, (int, float)) else [round_coords(x, nd) for x in c]


def first_point(geom: dict):
    c = geom["coordinates"]
    while isinstance(c[0], list):
        c = c[0]
    return c


def tipo_de(nombre: str) -> str:
    n = nombre.lower()
    return "Corregimiento" if any(k in n for k in CORREGIMIENTOS) else "Comuna"


def process(path: Path) -> None:
    gj = json.loads(path.read_text(encoding="utf-8"))
    if "error" in gj:
        raise SystemExit(f"El servidor respondió con un error: {gj['error']}")
    feats = gj.get("features") or []
    if not feats:
        raise SystemExit("El archivo no trae polígonos ('features' vacío).")

    # Debe ser la capa original del servidor (campos total_2018...total_2030), no el archivo
    # ya procesado de dashboard/data (ese trae pob_<año> y daría población 0 en silencio).
    props0 = {k.lower() for k in feats[0]["properties"]}
    if not any(k.startswith("total_") for k in props0):
        raise SystemExit(
            "Este GeoJSON no trae los campos total_<año> de la capa de población. "
            f"Campos encontrados: {sorted(props0)[:8]}... Usa la descarga original del servidor."
        )

    lon, lat = first_point(feats[0]["geometry"])[:2]
    if not (-77 < lon < -74 and 5 < lat < 8):
        raise SystemExit(
            f"Las coordenadas ({lon:.1f}, {lat:.1f}) no parecen longitud/latitud (EPSG:4326). "
            "Descarga la capa con outSR=4326 (la URL de este script ya lo trae)."
        )

    out, total_area, avisos = [], 0.0, 0
    for f in feats:
        p = {k.lower(): v for k, v in f["properties"].items()}
        nombre = str(p.get("nombre") or "").strip()
        if not nombre:
            raise SystemExit(f"Un polígono no tiene 'nombre'. Campos: {list(p)}")
        area = geom_area(f["geometry"]) / 1e6  # km²
        srv = p.get("st_area(shape)")
        if srv:
            ratio = (srv / 1e6) / area
            if not 0.97 < ratio < 1.03:
                avisos += 1
                print(f"  [aviso] {nombre}: st_area del servidor ({srv / 1e6:,.2f} km²) difiere de la "
                      f"geometría ({area:,.2f} km²); se usa la de la geometría")
        total_area += area
        props = {"nombre": nombre, "tipo": tipo_de(nombre), "area_km2": round(area, 3)}
        for y in YEARS:
            v = p.get(f"total_{y}")
            props[f"pob_{y}"] = int(v) if v is not None else None
        out.append({"type": "Feature",
                    "geometry": {"type": f["geometry"]["type"],
                                 "coordinates": round_coords(f["geometry"]["coordinates"])},
                    "properties": props})

    print(f"{len(out)} polígonos. Área total: {total_area:,.1f} km² "
          "(Medellín ≈ 380 km²; si está muy lejos, revisa la capa)")
    if not 340 < total_area < 420:
        print("  [aviso] el área total no está cerca de 380 km²: ¿la capa trae solo una parte "
              "o polígonos duplicados?")
    print(f"{'Nombre':<34}{'Tipo':<15}{'km²':>8}{'Pob 2024':>11}{'Hab/km²':>10}")
    for o in sorted(out, key=lambda x: -(x['properties']['pob_2024'] or 0) / x['properties']['area_km2']):
        q = o["properties"]
        d = (q["pob_2024"] or 0) / q["area_km2"]
        print(f"{q['nombre']:<34}{q['tipo']:<15}{q['area_km2']:>8.1f}{q['pob_2024'] or 0:>11,}{d:>10,.0f}")
    print(f"Población total 2024: {sum(o['properties']['pob_2024'] or 0 for o in out):,}")
    print("Verifica la columna 'Tipo': debe haber 5 corregimientos y el resto comunas.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps({"type": "FeatureCollection", "features": out},
                                   ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"escrito {OUT_FILE} ({OUT_FILE.stat().st_size / 1e3:,.0f} KB)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, help="GeoJSON local en vez de descargar")
    ap.add_argument("--refresh", action="store_true", help="volver a descargar aunque exista")
    args = ap.parse_args()
    if args.input:
        path = args.input
    elif RAW_FILE.exists() and not args.refresh:
        print(f"Usando {RAW_FILE} (usa --refresh para descargar de nuevo)")
        path = RAW_FILE
    else:
        path = download()
    process(path)


if __name__ == "__main__":
    main()
