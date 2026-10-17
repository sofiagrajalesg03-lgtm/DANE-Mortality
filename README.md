# Mortalidad en Colombia: dashboard (DANE, Estadísticas Vitales)


**Pregunta central:** ¿cómo ha cambiado la mortalidad en Colombia por departamento, sexo, edad y causa,
y qué se puede decir de Medellín?

Dashboard estático (HTML + Chart.js + Leaflet, sin servidor). Los datos se procesan con Python y se
publican como un JSON que el navegador filtra y suma.

## Estructura

```
mortalidad-colombia/
├── config.py                       # rutas y constantes compartidas
├── requirements.txt                # pandas, openpyxl
├── netlify.toml                    # publica solo dashboard/
├── data/
│   ├── raw/cuadros/                # anexos .xlsx del DANE (tú los copias aquí; no van a git)
│   ├── raw/medellin/               # capa de población descargada (no va a git)
│   └── processed/                  # intermedio en formato largo (no va a git)
├── scripts/
│   ├── 01_explore.py               # revisa los .xlsx y comprueba que el formato es el esperado
│   ├── 02_read_cuadros.py          # Cuadro 5 (tabla ancha) -> formato largo + validaciones
│   ├── 03_build_dashboard_data.py  # formato largo -> dashboard/data/datos.json
│   └── 04_medellin_density.py      # población y área por comuna -> medellin_densidad.geojson
└── dashboard/                      # lo que se publica en Netlify
    ├── index.html, app.js, styles.css
    ├── vendor/                     # Chart.js y Leaflet locales (sin CDN)
    └── data/                       # datos.json y medellin_densidad.geojson
```

## Cómo ejecutarlo

```bash
pip install -r requirements.txt

# 1. Copia en data/raw/cuadros/ los anexos del DANE (Cuadro 5 debe estar en cada .xlsx)
python scripts/01_explore.py            # ¿el formato es el esperado?
python scripts/02_read_cuadros.py       # ~30 s por archivo; falla si algún total no cuadra
python scripts/03_build_dashboard_data.py

# 2. (Pestaña Medellín: tasa, población y mapa) descarga la capa del Municipio
python scripts/04_medellin_density.py   # si falla la descarga, el script te dice qué URL abrir

# 3. Probar en local (no abras index.html con doble clic: el navegador bloquea fetch)
cd dashboard && python -m http.server 8000     # http://localhost:8000
```

Sin el paso 2 el dashboard funciona, pero en la pestaña Medellín la población, la densidad y la tasa
aparecen como "n/d" y el mapa muestra un aviso. Con él se activan los tres.

**Para agregar un año nuevo:** copia el .xlsx en `data/raw/cuadros/` y repite los pasos 01-03.
El año y si es parcial se leen del propio archivo.

## Despliegue (Netlify)

Conecta el repositorio: `netlify.toml` ya indica `publish = "dashboard"` y no hay paso de build. Antes de
publicar haz commit de `dashboard/data/datos.json` y de `dashboard/data/medellin_densidad.geojson`.

## Decisiones de análisis

- **Residencia, no ocurrencia.** Cada defunción se asigna al departamento/municipio donde residía el
  fallecido (Cuadro 5). La diferencia es real: en el anexo 2026pr, Antioquia tiene 24.742 defunciones por
  residencia y 24.977 por ocurrencia.
- **Conteos, no tasas, entre departamentos.** El ranking de departamentos no controla por población y
  el propio dashboard lo advierte. Solo Medellín tiene tasa, porque es la única población que cargamos.
- **Tasa de Medellín = defunciones ÷ población proyectada.** La población (Alcaldía de Medellín, proyección
  DANE con base en el Censo 2018, corte 30 de junio) no viene por sexo, así que no hay tasa por sexo.
- **Año parcial ≠ año completo.** El anexo 2026pr cubre enero-julio y es preliminar: se etiqueta, se
  dibuja más claro y no entra en variaciones anuales ni tasas.
- **El DANE publica mortalidad por municipio, no por comuna.** El mapa de Medellín muestra densidad, no
  mortalidad; no se inventa un cruce que los datos no permiten.
- **Causas:** lista 6/67 OPS (67 grupos). Algunos nombres traen erratas en un año; se identifica la causa
  por su código y se usa el nombre más frecuente.

### Hallazgos al validar los anexos (2024, 2025 y 2026pr)

- Son **cuadros agregados**, no microdatos: hay que pasar una tabla ancha (grupo de edad × sexo en
  columnas) a formato largo.
- En 2025 y 2026pr la fila de total de cada departamento trae el código `03000` (el nacional) en vez de
  `XX000`. Un lector que confíe en el código suma de más; por eso los bloques se identifican por nombre.
- Hay fallecidos con residencia en el **extranjero** o **sin información** de residencia (2,997 en 2025,
  1,1 % del total): no se asignan a un departamento y se muestran aparte.
- Validaciones que el pipeline exige: grupos de edad = total, departamentos + extranjero + sin
  información = nacional, las causas suman el total de cada bloque, y el cubo del dashboard coincide con
  los totales del DANE (nacionales y de Medellín) o no se escribe nada.

## Limitaciones conocidas

- Solo hay tres anexos (2024, 2025, 2026 ene-jul). Para una serie larga hacen falta más años en el mismo formato.
- No hay población por departamento, así que no hay tasas departamentales.
- Las cifras de 2025 y 2026 pueden cambiar cuando el DANE publique datos definitivos o actualice los preliminares.

## Fuentes

- DANE, Estadísticas Vitales (EEVV), defunciones no fetales. Anexos de cuadros de salida.
- Alcaldía de Medellín, capa "Población - Proyección (2018-2030) por comuna y corregimiento".
- Chart.js y Leaflet (licencias en `dashboard/vendor/`).
