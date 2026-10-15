# Mortalidad en Colombia — Dashboard (DANE, Estadísticas Vitales)

Proyecto 2 de la ruta: pasar de guardar datos a **analizarlos y comunicarlos**.

**Pregunta central:** ¿cómo ha cambiado la mortalidad en Colombia por departamento, sexo, edad y causa?

## Estructura

```
mortalidad-colombia/
├── requirements.txt
├── config.py                 # mapeo de columnas y rutas (edítalo tras explorar)
├── data/
│   ├── raw/                  # aquí van los archivos descargados del DANE (no se suben a git)
│   └── (processed en dashboard/data)
├── scripts/
│   ├── 01_explore.py         # inspecciona columnas, nulos y valores
│   └── 02_aggregate.py       # limpia y genera los JSON agregados
└── dashboard/                # carpeta que se publica en Netlify
    ├── index.html            # KPIs + gráficos + filtros (Chart.js)
    └── data/                 # JSON generados por 02_aggregate.py
```

## Pasos

1. Descarga los microdatos de defunciones no fetales (2015-2024 o los años que quieras)
   desde el catálogo de microdatos del DANE (`microdatos.dane.gov.co`, sección Estadísticas
   Vitales) y ponlos en `data/raw/`. Puede pedir registro gratuito.
2. `pip install -r requirements.txt`
3. `python scripts/01_explore.py` y revisa los nombres reales de las columnas.
4. Ajusta `COLS` en `config.py` según lo que viste.
5. `python scripts/02_aggregate.py` genera los JSON en `dashboard/data/`.
6. Prueba local: `cd dashboard && python -m http.server 8000`
7. Despliega la carpeta `dashboard/` en Netlify.

## Decisiones de análisis a documentar (esto es lo que cuentas en entrevista)

- Defunciones por lugar de **residencia** vs. de **ocurrencia** (cuál usas y por qué).
- Cifras preliminares vs. definitivas del último año.
- Valores faltantes o "sin información" en edad, sexo o municipio.
- Tasas vs. conteos: comparar departamentos solo por conteo engaña; si agregas población
  (proyecciones DANE) puedes calcular tasas por 100.000 hab.
- Agrupación de causas (lista 6/67 OMS/OPS) para que los gráficos sean legibles.

## Fuente

DANE, Estadísticas Vitales (EEVV). Citar siempre la fuente y el año de corte en el dashboard.
