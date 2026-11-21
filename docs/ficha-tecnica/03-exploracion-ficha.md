# 3. Exploración de los datos

## Cómo se exploró

- Conteo de nulos y marcas de "sin dato"
- Diagramas de caja y regla del rango intercuartil
- Formato y duplicados de claves
- Caja de Sonora, mapas y cruce espacial con municipios
- Revisión de codificación
- Cuadre contra totales y cifras de referencia

Herramientas: Python en notebooks de Jupyter; pandas, NumPy, Plotly, GeoPandas, Shapely, pyproj y pyogrio; pruebas con pytest.

## ITER: 7,500 filas → 7,300 localidades

Lo que dicen los datos:

- 4 localidades reúnen la mitad de la población: Hermosillo, Ciudad Obregón, Heroica Nogales y San Luis Río Colorado.
- El 93.9 % de las localidades tiene menos de 250 habitantes; ahí vive el 3.1 % de la población.
- En el estado, el 12.2 % tiene 60 años o más, el 4.9 % alguna discapacidad, el 18.6 % no tiene afiliación a servicios de salud y el 2.2 % habla lengua indígena. El 32.8 % de las viviendas no tiene auto ni moto.
- Los cinco indicadores son más altos en las localidades chicas. El caso más marcado es la lengua indígena: la habla el 10.5 % en las de menos de 250 habitantes y el 0.7 % en las de 15,000 o más.

| Tema | Qué se encontró | Qué se decidió |
|---|---|---|
| Faltantes | Indicadores confidenciales en 5,416 localidades (74.19 %), donde vive el 0.75 % de la población | A vacío y marcados; quedan indicadores para el 99.23 % de la población |
| Faltantes | Indicadores no disponibles en 31 localidades | A vacío y marcados |
| Atípicos | Solo altos, sobre todo en localidades chicas | No se borran |
| Lo que no cuadraba | Filas de totales | Se quitan |
| Lo que no cuadraba | Nombres repetidos | Unión por clave de localidad |
| Lo que no cuadraba | Viviendas colectivas | Marcadas |

## CLUES: 1,683 de Sonora → 917 fijos en operación

Lo que dicen los datos:

- 943 de los 1,683 registros de Sonora están en operación; el 44 % no lo está.
- Por nivel de atención: 777 de primer nivel, 103 de segundo, 6 de tercero y 57 con nivel NO APLICA (sin atención médica directa).
- 277 son consultorios junto a farmacia, todos privados: más de un tercio del primer nivel.
- Los 72 municipios tienen al menos un establecimiento en operación; 12 tienen solo uno.

Estas cifras son del notebook, sobre los 943 en operación. La tabla procesada tiene 917, sin las 14 unidades móviles ni los 12 que ya no operan: 756 de primer nivel, 52 con nivel NO APLICA y 267 consultorios junto a farmacia. Segundo y tercer nivel no cambian.

| Tema | Qué se encontró | Qué se decidió |
|---|---|---|
| Faltantes | "Sin dato" escrito como texto | A nulo |
| Faltantes | 11 con coordenadas vacías | Revisión manual |
| Atípicos | 56 con coordenadas fuera de Sonora; 55 son consultorios de farmacia con coordenadas en la Ciudad de México | Revisión manual |
| Lo que no cuadraba | 3 fuera de su municipio | Revisión manual |
| Lo que no cuadraba | De los 70 revisados: 58 verificadas y 12 que ya no operan | Los 12 se quitan |
| Lo que no cuadraba | Acentos y espacios desiguales | Mismo formato |

## Marco Geoestadístico: 16 capas → 3 tablas, 16,327 localidades

Lo que dicen los datos:

- 72 municipios de tamaño muy distinto: de 151.6 km² (San Felipe de Jesús) a 16,908.0 km² (Hermosillo), con mediana de 1,579.2 km².
- 16,327 localidades: 104 urbanas, 851 rurales amanzanadas y 15,372 rurales puntuales.
- Cada localidad cae en el municipio de su clave.

| Tema | Qué se encontró | Qué se decidió |
|---|---|---|
| Faltantes | Ninguno | — |
| Atípicos | Cada punto en su municipio | Sin cambio |
| Atípicos | 46 polígonos salen de su municipio, 3 por más de 1 m² | Sin cambio |
| Lo que no cuadraba | Proyección y codificación declaradas distinto | Fijadas al leer |
| Lo que no cuadraba | 851 localidades en dos capas | Marcadas |

## GACP: 189,432 del país → 7,300 de Sonora

Lo que dicen los datos:

- 3,078 localidades (42.2 %) están en grado Bajo o Muy bajo; ahí viven 78,453 personas (2.7 %).
- En 8 municipios toda la población está en esos grados: Bacadéhuachi, Bacerac, Bavispe, Granados, Huachinera, Huásabas, Nácori Chico y Villa Hidalgo. En número de personas van primero Navojoa (13,177) y Alamos (9,104).
- 4,388 localidades (60.1 %) no tienen transporte público o quedan a más de 2 horas de la cabecera municipal; ahí viven 127,954 personas (4.3 %).

| Tema | Qué se encontró | Qué se decidió |
|---|---|---|
| Faltantes | Ninguno | — |
| Atípicos | Distancia que no cuadra con el grado en localidades grandes | Se deja y se explica |
| Lo que no cuadraba | Categoría de transporte mezclada | Se explica |
| Lo que no cuadraba | Población del mismo censo que el ITER | Se descarta |

## Límites

- El tiempo al centro de servicios del GACP no es tiempo a salud.
- La distancia sola no indica aislamiento.
- Los porcentajes de localidades de menos de 50 habitantes cambian mucho.
- No se revisó el cruce de claves entre fuentes.

## Reglas de limpieza

Copiadas de los diccionarios. Son 14 de las 33; el resto está en cada diccionario.

### ITER

- Filas: se quitan los totales y acumulados (LOC 0000, 9998 y 9999). Quedan todas las localidades.
- Marcas: "*" y "N/D" pasan a vacío. La marca queda en disponibilidad.
- Porcentajes: conteo entre su denominador por 100, sin redondear. Quedan vacíos si falta el conteo o si el denominador es 0.
- vivienda_colectiva: más de 10 personas por vivienda habitada. Solo es una marca; no cambia la población.

### CLUES

- Textos: sin espacios al inicio ni al final, y con un solo espacio entre palabras.
- Pasan a nulo: "NO ESPECIFICADO", "SIN NÚMERO", "SIN NUMERO", "S/N", "SIN NOMBRE", los textos vacíos y el código postal 99999.
- Coordenadas: válidas si caen en la caja de latitud 26.0 a 32.6 y longitud −115.2 a −108.3. La caja es aproximada, no el límite real del estado. Las originales quedan en latitud_original y longitud_original.
- Revisión manual: se quitan los establecimientos con resultado FUERA DE OPERACION. En los de resultado VERIFICADA, latitud y longitud se toman del archivo y fuente_coordenada vale VERIFICADA; latitud_original y longitud_original no cambian. Una coordenada inválida que no esté en el archivo sigue como INVALIDA.

### Marco Geoestadístico

- Lectura: cada capa directo del zip con `/vsizip/`, sin extraerlo, con la codificación ISO-8859-1 y EPSG:6372 fijo.
- Filas: se conservan todas.
- Geometrías: completas, sin simplificar, en EPSG:6372 (metros).

### GACP

- Filas: se conservan todas.
- Categorías: en mayúsculas y sin acentos, como en SALUD-001, y ordenadas de mejor a peor acceso. transporte_publico usa las etiquetas cortas del EDA. Si aparece un valor fuera de las categorías esperadas o un nulo, el script se detiene en vez de dejar nulos.
- Columnas descartadas: OBJECTID (número interno del shapefile; no viene en los metadatos), NOM_ENT (siempre dice Sonora), CVE_LOC_n (repite CVE_LOC como número), POB_TOT (ver Preguntas sobre los datos) y la geometría.

## Diccionario de datos

Un diccionario por fuente, con las mismas secciones:

- Encabezado y selección de registros: fuente, fecha de descarga, archivos, script y qué filas se conservan.
- Columnas: tipo, descripción, valores posibles y columna original de cada una.
- Reglas de limpieza y reglas de calidad: lo que cambia el script y lo que comprueban las pruebas de `tests/`.
- Preguntas sobre los datos: dudas de interpretación con su respuesta, como por qué hay 917 establecimientos y no 929.

Ejemplo, del diccionario de CLUES:

| Columna | Tipo | Descripción | Valores posibles | Columna original |
|---|---|---|---|---|
| nivel_atencion | texto | Nivel de atención. | PRIMER NIVEL (756): consulta externa básica y prevención. SEGUNDO NIVEL (103): hospitales generales y clínicas de especialidades. TERCER NIVEL (6): alta especialidad. NO APLICA (52): sin atención médica directa. | NIVEL ATENCION |

Diccionarios: [ITER](../../references/diccionario_inegi-pop-001.md), [CLUES](../../references/diccionario_salud-001.md), [Marco Geoestadístico](../../references/diccionario_inegi-geo-001.md) y [GACP](../../references/diccionario_coneval-acc-001.md).

## Fuentes

| Fuente | Institución | Año o corte | Fecha de descarga |
|---|---|---|---|
| ITER (INEGI-POP-001) | INEGI | Censo 2020 | 12/10/2026 |
| CLUES (SALUD-001) | Secretaría de Salud | Archivo 202608, movimientos al 22/09/2026 | 11/10/2026 |
| Marco Geoestadístico (INEGI-GEO-001) | INEGI | 2025, referencia al 31/07/2025 | 13/10/2026 |
| GACP (CONEVAL-ACC-001) | CONEVAL | 2020, publicado el 15/06/2021 | 16/10/2026 |

El detalle y la fuente de cada cifra están en los notebooks de exploración ([ITER](../../notebooks/1.0-vh-eda-inegi-pop-001.ipynb), [CLUES](../../notebooks/1.0-vh-eda-salud-001.ipynb), [Marco Geoestadístico](../../notebooks/1.0-vh-eda-inegi-geo-001.ipynb) y [GACP](../../notebooks/1.0-vh-eda-coneval-acc-001.ipynb)) y en los diccionarios de [`references/`](../../references/); las fechas de descarga, en [`catalog/ingestions.csv`](../../catalog/ingestions.csv).
