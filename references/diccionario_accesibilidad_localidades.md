# Diccionario de datos: tabla final de accesibilidad

Accesibilidad geográfica a servicios de salud de cada localidad de Sonora: el establecimiento de 1er y de 2do nivel más cercano por carretera, la distancia y el tiempo de traslado, y las variables de vulnerabilidad de la localidad. Una fila por localidad. Es la tabla que usan el tablero (`app.py`) y el notebook de análisis (`notebooks/2.0-dd-analisis-accesibilidad.ipynb`).

- Fuentes: INEGI-POP-001 (ITER 2020), SALUD-001 (CLUES, con la revisión manual de coordenadas), CONEVAL-ACC-001 (GACP 2020) e INEGI-ROUTE-001 (API de Ruteo SAKBÉ v3.1). Ver sus diccionarios en `references/`.
- Script: `src/health_data/processing/ruteo.py`
- Archivo procesado: `data/processed/accesibilidad_localidades.parquet`
- Generación sin consultar SAKBÉ (usa solo las rutas en caché): `make data`, o `PYTHONPATH=src python -m health_data.processing.ruteo`
- Consulta de rutas faltantes a SAKBÉ (gasta cuota): `make rutas`, o `PYTHONPATH=src python -m health_data.processing.ruteo --sakbe`
- Caché de rutas: `data/interim/sakbe_cache.sqlite`. Requiere tokens en `.env` (ver `.env.example`).
- Fechas de consulta a SAKBÉ: del 16/10/2026 al 18/10/2026.

## Selección de registros

- Parte de las 7,300 localidades del ITER (INEGI-POP-001) y excluye las 3 de la Isla del Tiburón (16 habitantes), que no tienen acceso por carretera. La lista y el motivo están en `config/fuentes_health.yaml` (`localidades_excluidas`). Quedan 7,297 localidades con 2,944,824 habitantes.
- Establecimientos: los 917 de SALUD-001 en operación y fijos (sin unidades móviles), con coordenada de CLUES (859) o verificada a mano (58). Se separan en 1er nivel (nivel PRIMER o tipo DE CONSULTA EXTERNA) y 2do nivel (nivel SEGUNDO o TERCER, o tipo DE HOSPITALIZACION).
- Por origen del tiempo (`routing_status`): ok 7,213, parcial 28 y sin_ruta 56.

## Cómo se calcula el tiempo

1. Para cada localidad y nivel se eligen los 2 establecimientos más cercanos en línea recta.
2. Con SAKBÉ se ubica el tramo de carretera más cercano a la localidad y a cada establecimiento (escalas de búsqueda 50,000, 250,000 y 1,000,000), y se calcula la ruta óptima para automóvil. Se conserva la de menor tiempo.
3. Si la localidad y el establecimiento quedan sobre el mismo tramo, o SAKBÉ responde que origen y destino son el mismo punto, el trayecto es local: distancia en línea recta a 35 km/h, con un mínimo de 3 minutos.
4. Si no hay ruta SAKBÉ para un nivel (la localidad no tiene carretera cercana o SAKBÉ no ubica a sus candidatos), se usa el respaldo con CONEVAL: la mediana del tiempo y la distancia medidos con SAKBÉ en las localidades del mismo municipio y con la misma categoría de `tiempo_centro_servicios`; si son menos de 5, la mediana estatal de esa categoría.
5. El tiempo al 1er nivel no puede ser mayor que el tiempo al hospital, porque el hospital también da atención básica: se toma el menor de los dos.

## Columnas

| Columna | Tipo | Descripción | Valores posibles | Origen |
|---|---|---|---|---|
| locality_id | texto | Clave geográfica de la localidad, de 9 dígitos. Llave para unir con las demás fuentes. | 7,297 claves únicas. Empieza con 26. | cvegeo de INEGI-POP-001 |
| locality_name | texto | Nombre de la localidad. No sirve como llave: hay nombres repetidos. | 5,703 nombres distintos. | localidad de INEGI-POP-001 |
| municipality_name | texto | Nombre del municipio. | 72 municipios. | municipio de INEGI-POP-001 |
| population | entero | Población total. | 1 a 855,563. Suma 2,944,824. | poblacion_total de INEGI-POP-001 |
| latitude | decimal | Latitud en grados decimales. | 26.31 a 32.49 | latitud de INEGI-POP-001 |
| longitude | decimal | Longitud en grados decimales. | −115.02 a −108.48 | longitud de INEGI-POP-001 |
| nearest_primary_clues | texto | CLUES del establecimiento de 1er nivel con menor tiempo por carretera. En los niveles con respaldo CONEVAL es el más cercano en línea recta. | 496 establecimientos distintos. | clues de SALUD-001 |
| primary_distance_km | decimal | Distancia por carretera a ese establecimiento, en km. | 0 a 243.15. Mediana 9.73. | SAKBÉ (`long_km`) o respaldo CONEVAL |
| primary_time_min | decimal | Tiempo de traslado en automóvil al 1er nivel, en minutos. Nunca mayor que secondary_time_min. | 3 a 413. Mediana 12.4. | SAKBÉ (`tiempo_min`) o respaldo CONEVAL |
| primary_method | texto | Origen del tiempo al 1er nivel. | sakbe (7,213), coneval (84). estimado solo en localidades aún no consultadas. | Derivada |
| nearest_secondary_clues | texto | CLUES del establecimiento de 2do nivel (hospital) con menor tiempo por carretera. En los niveles con respaldo CONEVAL es el más cercano en línea recta. | 71 establecimientos distintos. | clues de SALUD-001 |
| secondary_distance_km | decimal | Distancia por carretera a ese hospital, en km. | 0.28 a 369.05. Mediana 31.85. | SAKBÉ o respaldo CONEVAL |
| secondary_time_min | decimal | Tiempo de traslado en automóvil al 2do nivel, en minutos. | 3 a 413. Mediana 33.1. | SAKBÉ o respaldo CONEVAL |
| secondary_method | texto | Origen del tiempo al 2do nivel. | sakbe (7,241), coneval (56). | Derivada |
| routing_status | texto | Origen de los tiempos de la localidad. | ok (7,213): ambos niveles por SAKBÉ. parcial (28): solo un nivel por SAKBÉ y el otro por CONEVAL. sin_ruta (56): ningún nivel por SAKBÉ; ambos por CONEVAL. estimado: aún no consultada (no hay en la tabla actual). | Derivada |
| routing_consulted_at | texto | Fecha y hora de la consulta a SAKBÉ más reciente entre los dos niveles (ISO 8601). | 16/10/2026 a 18/10/2026. Vacía en las 56 sin_ruta. | SAKBÉ |
| disponibilidad | texto | Si ITER publica los indicadores de la localidad. | COMPLETA (1,853), CONFIDENCIAL (5,413), NO DISPONIBLE (31). | INEGI-POP-001 |
| poblacion_60_y_mas | entero | Personas de 60 años y más. | 0 a 97,155. Vacía en 5,444. | INEGI-POP-001 |
| pct_60_y_mas | decimal | Porcentaje de personas de 60 años y más. | 0 a 100. Vacío en 5,444. | INEGI-POP-001 |
| poblacion_con_discapacidad | entero | Personas con discapacidad. | 0 a 37,201. Vacía en 5,444. | INEGI-POP-001 |
| pct_con_discapacidad | decimal | Porcentaje de personas con discapacidad. | 0 a 66.67. Vacío en 5,444. | INEGI-POP-001 |
| poblacion_sin_afiliacion | entero | Personas sin afiliación a servicios de salud. | 0 a 141,866. Vacía en 5,444. | INEGI-POP-001 |
| pct_sin_afiliacion | decimal | Porcentaje de personas sin afiliación a servicios de salud. | 0 a 100. Vacío en 5,444. | INEGI-POP-001 |
| poblacion_lengua_indigena | entero | Personas de 3 años y más que hablan una lengua indígena. | 0 a 4,012. Vacía en 5,444. | INEGI-POP-001 |
| pct_lengua_indigena | decimal | Porcentaje de personas de 3 años y más que hablan una lengua indígena. | 0 a 100. Vacío en 5,444. | INEGI-POP-001 |
| viviendas_habitadas | entero | Viviendas habitadas. | 1 a 258,273. | INEGI-POP-001 |
| viviendas_sin_auto_ni_moto | entero | Viviendas particulares habitadas sin automóvil, camioneta, motocicleta ni motoneta. | 0 a 73,109. Vacía en 5,444. | INEGI-POP-001 |
| pct_viviendas_sin_auto_ni_moto | decimal | Porcentaje de viviendas sin automóvil ni motocicleta. | 0 a 100. Vacío en 5,447. | INEGI-POP-001 |
| grado_accesibilidad | categoría ordenada | Grado de accesibilidad a carretera pavimentada. | MUY ALTO (866), ALTO (2,695), MEDIO (661), BAJO (2,626), MUY BAJO (449). | CONEVAL-ACC-001 |
| transporte_publico | categoría ordenada | Transporte público y tiempo en él a la cabecera municipal. | 5 categorías, de mejor a peor (ver el diccionario de CONEVAL-ACC-001). | CONEVAL-ACC-001 |
| tiempo_centro_servicios | categoría ordenada | Tiempo al centro de servicios (localidad de 15,000 habitantes o más) más cercano. Es la base del respaldo CONEVAL. | MENOS DE 1 HR. (4,602), 1 A 2 HRS. (1,556), 2 A 3 HRS. (652), 3 A 4 HRS. (297), MAS DE 4 HRS. (190). | CONEVAL-ACC-001 |
| distancia_carretera | categoría ordenada | Distancia aproximada a carretera pavimentada, en metros. | <= 1,000 (3,202), > 1,000 Y < 2,000 (1,056), >= 2,000 (3,039). | CONEVAL-ACC-001 |
| pct_sin_auto | decimal | Igual a pct_viviendas_sin_auto_ni_moto. Se conserva por compatibilidad. | Igual. | Derivada |
| poblacion_discapacidad | entero | Igual a poblacion_con_discapacidad. Se conserva por compatibilidad. | Igual. | Derivada |

Las variables de vulnerabilidad vienen vacías en las localidades CONFIDENCIAL y NO DISPONIBLE de ITER (5,444), que reúnen al 0.8 % de la población.

## Indicadores que se calculan sobre esta tabla

Están en `src/health_data/analisis.py`. Una localidad tiene **acceso comprometido** si `primary_time_min` supera el umbral de 1er nivel (60 min) o `secondary_time_min` el de 2do nivel (120 min). Los umbrales están en `config/fuentes_health.yaml`.

- Población por rango de tiempo (`poblacion_por_rango`).
- Indicadores por municipio, con tiempos ponderados por población (`resumen_municipal`).
- Localidades con acceso comprometido, de mayor a menor población (`localidades_prioritarias`).
- Grupos vulnerables con acceso comprometido (`grupos_vulnerables`). La población sin vehículo se estima como `population × pct_viviendas_sin_auto_ni_moto / 100`.

## Reglas de calidad

El pipeline las revisa en cada ejecución (`src/health_data/validacion.py`) y guarda el resultado en `data/processed/manifiesto.json`:

- Están las columnas requeridas.
- locality_id es única.
- Las coordenadas caen en el rectángulo de Sonora.
- No hay tiempos negativos en primary_time_min ni en secondary_time_min.
- Consistencia entre niveles (informativa): cuenta en cuántas localidades el hospital queda más cerca que el centro de salud. Que primary_time_min nunca supere a secondary_time_min lo garantiza el cálculo (paso 5).
- Cobertura de SAKBÉ: al menos 70 % de las localidades en ok. Hoy: 98.8 %.

Además, `tests/test_ruteo.py` y `tests/test_analisis.py` prueban el cálculo con datos simulados.

## Preguntas sobre los datos

- ¿Los tiempos incluyen esperar o ser atendido? No. Son de traslado en automóvil en condiciones óptimas, según SAKBÉ. No incluyen el tiempo dentro del establecimiento, transporte público ni el estado del camino.
- ¿Por qué tantas localidades con 3 minutos? Porque tienen un centro de salud en la propia localidad o sobre el mismo tramo de carretera; 3 minutos es el mínimo. Son 659 localidades con el 93 % de la población.
- ¿Por qué primary_time_min es igual a secondary_time_min en 1,025 localidades? Porque el hospital está a la misma distancia o más cerca que el centro de salud, y el hospital también da atención básica. nearest_primary_clues sigue siendo el centro de salud más cercano.
- ¿Qué tan confiable es el respaldo CONEVAL? Se probó contra las rutas reales, excluyendo a cada localidad de su propia mediana: en localidades a 2 km o más de carretera pavimentada acierta si la localidad supera el umbral en ~91 % de los casos para el hospital y ~84 % para el centro de salud, contra ~72 % de la estimación por línea recta, que subestima unos 40 y 17 minutos.
- ¿Por qué hay 28 localidades parcial? Sus 2 centros de salud candidatos no se pudieron ubicar en la red de SAKBÉ: 3 establecimientos de Hermosillo sin ningún tramo de calle cerca y los centros de salud de Sásabe y Sáric, para los que SAKBÉ responde vacío con ciertos orígenes. Tienen ruta SAKBÉ al hospital.
- ¿Cuál es el tiempo más alto? 413 minutos, en Charco de Piedra (Pitiquito), de 1 habitante.
- ¿Se puede citar? Las condiciones de uso de la API de Ruteo piden citar a INEGI y a la API de Ruteo en todo resultado difundido, por ejemplo: "Fuente: INEGI, API de Ruteo SAKBÉ v3.1 (consultas del 16 al 18 de octubre de 2026)".
