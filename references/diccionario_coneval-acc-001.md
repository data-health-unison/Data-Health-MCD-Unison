# Diccionario de datos: CONEVAL-ACC-001

Grado de accesibilidad a carretera pavimentada (GACP) 2020 de CONEVAL para las localidades de Sonora. Una fila por localidad.

- Fuente: CONEVAL, Grado de accesibilidad a carretera pavimentada a nivel localidad, publicado el 15/06/2021. CONEVAL desapareció en 2025; el INEGI resguarda sus datos.
- Página: https://www.coneval.org.mx/Medicion/Paginas/Grado_accesibilidad_carretera.aspx
- Metodología: https://www.coneval.org.mx/Medicion/MP/Documents/Accesibilidad_carretera/2020/Documento_metodologico_GACP_2020.pdf
- Descarga: https://www.coneval.org.mx/Medicion/MP/Documents/Accesibilidad_carretera/2020/Shapefile_localidades_componentes_GACP_CONEVAL.zip
- Fecha de descarga: 16/10/2026
- Archivo crudo: `data/raw/coneval_gacp2020_localidades.zip`, shapefile `Localidades_componentes_GACP_CONEVAL` (solo sus atributos)
- Script: `src/health_data/processing/coneval_acc_001.py`
- Archivo procesado: `data/processed/coneval-acc-001_localidades.parquet`
- Generación en Bash: `PYTHONPATH=src python -m health_data.processing.coneval_acc_001`
- Generación en PowerShell: `$env:PYTHONPATH="src"; python -m health_data.processing.coneval_acc_001`

Las uniones con el ITER, el Marco Geoestadístico y CLUES se hacen por cvegeo, nunca por nombre: 246 nombres de localidad se repiten dentro de su municipio, en 605 localidades. Además, el archivo escribe Alamos y Onavas sin acento.

## Selección de registros

- El archivo es nacional, con 189,432 localidades. Se leen las de Sonora (CVE_ENT 26): 7,300 localidades en 72 municipios. Se conservan todas.
- Solo se leen los atributos. La geometría, un punto por localidad, no se usa.
- Las cifras son las del GACP 2020.

## Columnas

| Columna | Tipo | Descripción | Valores posibles | Columna original |
|---|---|---|---|---|
| cvegeo | texto | Clave geográfica de la localidad, de 9 dígitos: entidad, municipio y localidad. Sirve para unir con el ITER, el Marco Geoestadístico y CLUES. | 7,300 claves únicas. Empieza con 26. | CVE_LOC |
| cve_ent | texto | Clave de la entidad, 2 dígitos. | 26 | Dígitos 1 y 2 de CVE_LOC, iguales a CVE_ENT |
| cve_mun | texto | Clave del municipio, 3 dígitos. | 001 a 072. Hay localidades en los 72. | Dígitos 3 a 5 de CVE_LOC; con la entidad, iguales a CVE_MUN |
| cve_loc | texto | Clave de la localidad, 4 dígitos. | 0001 a 4133 | Dígitos 6 a 9 de CVE_LOC |
| municipio | texto | Nombre del municipio. Solo para mostrar. | 72 nombres. Alamos y Onavas vienen sin acento. | NOM_MUN |
| localidad | texto | Nombre de la localidad, sin espacios sobrantes. Solo para mostrar; no sirve como llave. | Texto libre. 5,706 nombres distintos. 259 empiezan con "Ninguno" (ver Preguntas sobre los datos). | NOM_LOC |
| grado_accesibilidad | categoría ordenada | Grado de accesibilidad a carretera pavimentada. | MUY ALTO (866), ALTO (2,695), MEDIO (661), BAJO (2,626), MUY BAJO (452). | GACP |
| transporte_publico | categoría ordenada | Disponibilidad de transporte público y tiempo de traslado en él a la cabecera municipal. | 5 categorías, en la tabla de abajo. | C_TP |
| tiempo_centro_servicios | categoría ordenada | Tiempo aproximado al centro de servicios más cercano, es decir, a una localidad de 15,000 habitantes o más. | MENOS DE 1 HR. (4,602), 1 A 2 HRS. (1,556), 2 A 3 HRS. (652), 3 A 4 HRS. (297), MAS DE 4 HRS. (193). | C_CS |
| distancia_carretera | categoría ordenada | Distancia aproximada a una carretera pavimentada, en metros. | <= 1,000 (3,202), > 1,000 Y < 2,000 (1,056), >= 2,000 (3,042). | C_DIS |

Las cuatro categorías van de mejor a peor acceso y se pueden comparar. Por ejemplo, `grado_accesibilidad >= "BAJO"` da las BAJO y las MUY BAJO.

### Categorías de transporte_publico

| Etiqueta | Texto en el crudo | Localidades |
|---|---|---|
| 2,500 HAB. O MAS, CABECERA O MENOS DE 20 MIN | Localidades con 2,500 habitantes o más, o que son cabecera municipal o que el tiempo de traslado en transporte público a cabecera municipal es menor a 20 minutos | 251 |
| 20 MIN A 1 H | Tiempo de traslado en transporte público a cabecera municipal de 20 minutos a 1 hora | 610 |
| MAS DE 1 H A 1.5 H | Tiempo de traslado en transporte público a cabecera municipal de más de 1 hora a 1.5 horas | 147 |
| MAS DE 1.5 H A 2 H, O NO ESPECIFICADA | Tiempo de traslado en transporte público a cabecera municipal de más de 1.5 horas a 2 horas, o con disponibilidad y tiempo de traslado no especificada | 1,904 |
| SIN TRANSPORTE PUBLICO O MAS DE 2 H | Sin transporte público, o tiempos de traslado en transporte público mayor de 2 horas a cabecera municipal | 4,388 |

## Reglas de limpieza

- Lectura: los atributos de Sonora, directo del zip con `/vsizip/` y sin extraerlo, con `geopandas.read_file(..., where="CVE_ENT = '26'", ignore_geometry=True)`. CVE_ENT tiene que estar entre las columnas leídas: sin ella, el filtro devuelve 0 filas sin error. Si no se lee ninguna localidad, el script se detiene.
- Filas: se conservan todas.
- Claves: texto con sus ceros a la izquierda, separadas de CVE_LOC. El script se detiene si CVE_LOC no tiene 9 dígitos o si no empieza con CVE_ENT y CVE_MUN.
- Categorías: en mayúsculas y sin acentos, como en SALUD-001, y ordenadas de mejor a peor acceso. transporte_publico usa las etiquetas cortas del EDA. Si aparece un valor fuera de las categorías esperadas o un nulo, el script se detiene en vez de dejar nulos.
- Nombres (municipio y localidad): como vienen, solo sin espacios al inicio ni al final y con un solo espacio entre palabras. Se corrigieron 8 nombres de localidad con dos espacios seguidos, como "San Judas (El Naranjal)", que traía dos espacios antes del paréntesis. No se corrigen acentos: Alamos y Onavas se quedan así. "Ninguno" no pasa a nulo.
- Columnas descartadas: OBJECTID (número interno del shapefile; no viene en los metadatos), NOM_ENT (siempre dice Sonora), CVE_LOC_n (repite CVE_LOC como número), POB_TOT (ver Preguntas sobre los datos) y la geometría.

## Reglas de calidad

Están en `tests/test_coneval_acc_001.py` y se omiten si falta el archivo procesado. No usan conteos fijos.

- La tabla tiene exactamente sus 10 columnas, en orden.
- cvegeo única, de 9 dígitos, que empieza con 26 y es igual a cve_ent + cve_mun + cve_loc. cve_ent de 2 dígitos, cve_mun de 3 y cve_loc de 4.
- Municipios con claves de 001 a 072, sin faltantes ni sobrantes.
- Las cuatro categorías, al leer el Parquet, están ordenadas, traen exactamente las categorías esperadas en su orden y no tienen nulos.
- Cada combinación de los tres componentes da un solo grado.
- Sin nulos en cvegeo, cve_ent, cve_mun, cve_loc, municipio y localidad.
- Ningún municipio ni localidad trae Ã, Â o el carácter de reemplazo (�), que son señales de mala codificación.
- Ningún nombre tiene espacios al inicio, al final ni dos seguidos.

## Preguntas sobre los datos

- ¿Qué mide cada componente? transporte_publico mide si hay transporte público y cuánto tarda en llegar a la cabecera municipal; se midió con una encuesta del INEGI a las localidades de menos de 2,500 habitantes que no son cabecera municipal; las de 2,500 o más y las cabeceras quedan en la primera categoría (metodología, cuadro 5). tiempo_centro_servicios mide el tiempo aproximado al centro de servicios más cercano. distancia_carretera mide la distancia aproximada a una carretera pavimentada.
- ¿Qué es un centro de servicios? Según la metodología (cuadro 6), una localidad de 15,000 habitantes o más. Por eso tiempo_centro_servicios no es el tiempo a un establecimiento de salud.
- ¿Cómo se forma el grado? Con los tres componentes. En Sonora aparecen 64 de las 75 combinaciones posibles, y cada una da un solo grado. Las 2,626 localidades BAJO están a 2,000 m o más de una carretera pavimentada, y las 452 MUY BAJO están a 3 horas o más de un centro de servicios: 259 de 3 a 4 horas y 193 a más de 4 (EDA, sección 4).
- ¿La distancia sola indica aislamiento? No. El archivo trae la distancia medida; para el grado, la metodología asignó el mejor valor a las localidades de 15,000 habitantes o más, porque son urbanas. Según el EDA, 8 de las 15 aparecen a 2,000 m o más y las 15 son MUY ALTO (sección 4).
- ¿Qué junta la cuarta categoría de transporte? MAS DE 1.5 H A 2 H, O NO ESPECIFICADA junta dos casos: un tiempo de más de 1.5 a 2 horas, y una disponibilidad o un tiempo de traslado no especificados. No se pueden separar. Según la metodología, las no especificadas son localidades en las que la encuesta no reportó el tiempo de traslado. Tiene 1,904 localidades.
- ¿Por qué no trae población? El crudo trae POB_TOT ("Población INEGI, 2020"), pero la población del proyecto sale del ITER (INEGI-POP-001), que se une por cvegeo. Así hay una sola fuente de población.
- ¿Qué significa "Ninguno"? No es un nulo. Es la regla del INEGI para las localidades sin nombre geográfico: "Cuando la localidad carezca de nombre geográfico se le asignará el vocablo Ninguno y una referencia entre corchetes" (Guía de aplicación de la Norma Técnica del Marco Geoestadístico, sección 4.4.2.2.2, inciso a, criterio 6: https://ceieg.veracruz.gob.mx/wp-content/uploads/sites/21/2025/06/AnexoIII_ntmg2025.pdf). Hay 259 localidades "Ninguno": 62 sin referencia y 197 con una, como "Ninguno [Familia Zamarrón]". En una de ellas la referencia va pegada, sin espacio antes del corchete.
- ¿Qué licencia tiene? CC BY-NC 2.5 MX: no se permite usar los datos con fines de lucro y se debe citar la fuente. Así lo dice la sección 1.8 de `Metadato_localidades_GACP_CONEVAL.txt`, que viene en el zip. Licencia completa: http://creativecommons.org/licenses/by-nc/2.5/mx/
