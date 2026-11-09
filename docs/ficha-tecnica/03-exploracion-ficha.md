# 3. Exploración de los datos

## Técnicas y herramientas

Técnicas: conteo de nulos y marcas de "sin dato"; diagramas de caja y regla del rango intercuartil; formato y duplicados de claves; caja de Sonora, mapas y cruce espacial con municipios; revisión de codificación; cuadre contra totales y cifras de referencia.

Herramientas: Python en notebooks de Jupyter; pandas, NumPy, Plotly, GeoPandas, Shapely, pyproj y pyogrio; pruebas con pytest.

## Fuentes

| Fuente | Institución | Año o corte | Fecha de descarga |
|---|---|---|---|
| ITER (INEGI-POP-001) | INEGI | Censo 2020 | 12/10/2026 |
| CLUES (SALUD-001) | Secretaría de Salud | Archivo 202608, movimientos al 22/09/2026 | 11/10/2026 |
| Marco Geoestadístico (INEGI-GEO-001) | INEGI | 2025, referencia al 31/07/2025 | 13/10/2026 |
| GACP (CONEVAL-ACC-001) | CONEVAL | 2020, publicado el 15/06/2021 | 16/10/2026 |

## Resumen

| Fuente | Entrada → salida | Faltantes | Atípicos | Lo que no cuadraba |
|---|---|---|---|---|
| ITER | 7,500 filas → 7,300 localidades | Confidenciales o no disponibles: a vacío y marcados; indicadores para el 99.23 % de la población | Solo altos, sobre todo en localidades chicas: no se borran | Filas de totales: se quitan; nombres repetidos: unión por clave de localidad; viviendas colectivas: marcadas |
| CLUES | 1,683 de Sonora → 917 fijos en operación | "Sin dato" escrito como texto: a nulo; coordenadas vacías: revisión manual | Coordenadas fuera de Sonora: revisión manual | Fuera de su municipio: revisión manual. De los 70 revisados: 58 verificadas; 12 ya no operan: se quitan. Acentos y espacios desiguales: mismo formato |
| Marco Geoestadístico | 16 capas → 3 tablas, 16,327 localidades | Ninguno | Cada punto en su municipio; 46 polígonos salen de su municipio, 3 por más de 1 m²: sin cambio | Proyección y codificación declaradas distinto: fijadas al leer; 851 localidades en dos capas: marcadas |
| GACP | 189,432 del país → 7,300 de Sonora | Ninguno | Distancia que no cuadra con el grado en localidades grandes: se deja y se explica | Categoría de transporte mezclada: se explica; población del mismo censo que el ITER: se descarta |

Límites: el tiempo al centro de servicios del GACP no es tiempo a salud; la distancia sola no indica aislamiento; los porcentajes de localidades de menos de 50 habitantes cambian mucho; no se revisó el cruce de claves entre fuentes.

> Figura opcional: mapa de los 917 establecimientos.

El detalle y la fuente de cada cifra están en los notebooks de exploración, `notebooks/1.0-vh-eda-*.ipynb`, y en los diccionarios de `references/`; las fechas de descarga, en `catalog/ingestions.csv`.
