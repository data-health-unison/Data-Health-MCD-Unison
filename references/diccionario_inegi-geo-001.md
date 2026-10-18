# Diccionario de datos: INEGI-GEO-001

Municipios y localidades de Sonora del Marco Geoestadístico 2025 del INEGI, con su geometría. Son tres tablas: una fila por municipio, una por localidad amanzanada y una por localidad puntual.

- Fuente: INEGI, Marco Geoestadístico 2025 (producto 794551163061), con fecha de referencia 31/07/2025
- Página: https://www.inegi.org.mx/app/biblioteca/ficha.html?upc=794551163061
- Descarga: https://www.inegi.org.mx/contenidos/productos/prod_serv/contenidos/espanol/bvinegi/productos/geografia/marcogeo/794551163061/26_sonora.zip
- Fecha de descarga: 13/10/2026
- Archivo crudo: `data/raw/mg2025_26_sonora.zip`, capas `26mun`, `26l` y `26lpr` de la carpeta `conjunto_de_datos/`
- Script: `src/health_data/processing/inegi_geo_001.py`
- Archivos procesados: `data/processed/inegi-geo-001_municipios.parquet`, `data/processed/inegi-geo-001_localidades_amanzanadas.parquet` y `data/processed/inegi-geo-001_localidades_puntuales.parquet`, en GeoParquet y EPSG:6372. Se leen con `geopandas.read_parquet`.
- Generación en Bash: `PYTHONPATH=src python -m health_data.processing.inegi_geo_001`
- Generación en PowerShell: `$env:PYTHONPATH="src"; python -m health_data.processing.inegi_geo_001`

Para qué sirve cada tabla:

- Municipios: validar que una coordenada caiga en su municipio y hacer mapas por municipio.
- Localidades amanzanadas: ubicar establecimientos dentro de una localidad, con su polígono, y hacer mapas.
- Localidades puntuales: ubicar establecimientos en localidades rurales por cercanía al punto y hacer mapas.

Las uniones con el ITER y CLUES se hacen por cvegeo, nunca por nombre: 2,108 de las 16,327 localidades comparten nombre con otra de su municipio. Por ejemplo, en Hermosillo hay 12 localidades llamadas San Francisco y 10 San José.

## Selección de registros

- Se conservan todas las filas de las tres capas: 72 municipios, 955 localidades amanzanadas (104 urbanas y 851 rurales) y 16,223 localidades puntuales.
- Localidades puntuales por plano: NO 15,095, SI 851 y CROQUIS 277.
- 851 localidades están en las dos tablas de localidades. Sin repetirlas, hay 16,327.
- No se generan el contorno del estado (es la unión de los municipios), las otras 11 capas del zip ni un GeoJSON simplificado. Eso irá con los mapas.
- Las cifras cambian con cada versión del Marco Geoestadístico.

## Columnas

### inegi-geo-001_municipios.parquet

| Columna | Tipo | Descripción | Valores posibles | Columna original |
|---|---|---|---|---|
| cvegeo | texto | Clave geográfica del municipio, de 5 dígitos: entidad y municipio. | 26001 a 26072. Sin repetidos. | CVEGEO |
| cve_ent | texto | Clave de la entidad, 2 dígitos. | 26 | CVE_ENT |
| cve_mun | texto | Clave del municipio, 3 dígitos. | 001 a 072 | CVE_MUN |
| municipio | texto | Nombre del municipio. | 72 nombres. | NOMGEO |
| area_km2 | decimal | Área en km², medida en EPSG:6372. | 151.6 (San Felipe de Jesús) a 16,908.0 (Hermosillo). Suman 180,633.8. | Derivada de la geometría |
| geometry | geometría | Límite del municipio, en metros (EPSG:6372). | 68 polígonos y 4 multipolígonos. | Geometría de 26mun |

### inegi-geo-001_localidades_amanzanadas.parquet

| Columna | Tipo | Descripción | Valores posibles | Columna original |
|---|---|---|---|---|
| cvegeo | texto | Clave geográfica de la localidad, de 9 dígitos: entidad, municipio y localidad. Sirve para unir con el ITER y CLUES. | 955 claves únicas. Empieza con 26. | CVEGEO |
| cve_ent | texto | Clave de la entidad, 2 dígitos. | 26 | CVE_ENT |
| cve_mun | texto | Clave del municipio, 3 dígitos. | 001 a 072. Hay localidades amanzanadas en los 72. | CVE_MUN |
| cve_loc | texto | Clave de la localidad, 4 dígitos. | 0001 a 4150 | CVE_LOC |
| municipio | texto | Nombre del municipio, tomado de la tabla de municipios por cve_mun. | 72 municipios. | Derivada de CVE_MUN y 26mun |
| localidad | texto | Nombre de la localidad, sin espacios sobrantes. No sirve como llave. | Texto libre. 918 nombres distintos. | NOMGEO |
| ambito | texto | Ámbito de la localidad. | URBANA (104), RURAL (851). | AMBITO |
| area_km2 | decimal | Área del polígono en km², medida en EPSG:6372. | 0.013 a 204.718. Mediana de 1.788 en las urbanas y de 0.242 en las rurales. | Derivada de la geometría |
| geometry | geometría | Polígono de la localidad, en metros (EPSG:6372). | 942 polígonos y 13 multipolígonos. | Geometría de 26l |

### inegi-geo-001_localidades_puntuales.parquet

| Columna | Tipo | Descripción | Valores posibles | Columna original |
|---|---|---|---|---|
| cvegeo | texto | Clave geográfica de la localidad, de 9 dígitos: entidad, municipio y localidad. Sirve para unir con el ITER y CLUES. | 16,223 claves únicas. Empieza con 26. | Primeros 9 dígitos de CVEGEO |
| cve_ent | texto | Clave de la entidad, 2 dígitos. | 26 | CVE_ENT |
| cve_mun | texto | Clave del municipio, 3 dígitos. | 001 a 072. Hay localidades puntuales en los 72. | CVE_MUN |
| cve_loc | texto | Clave de la localidad, 4 dígitos. | 0002 a 4210 | CVE_LOC |
| cve_ageb | texto | Clave del AGEB donde está la localidad: 3 dígitos y un dígito o una letra. | 1,031 claves distintas. 1,161 localidades tienen una con letra, como 017A. | CVE_AGEB |
| municipio | texto | Nombre del municipio, tomado de la tabla de municipios por cve_mun. | 72 municipios. | Derivada de CVE_MUN y 26mun |
| localidad | texto | Nombre de la localidad, sin espacios sobrantes. No sirve como llave. | Texto libre. 405 empiezan con "Ninguno" (ver Preguntas sobre los datos). | NOMGEO |
| plano | texto | Si la localidad tiene plano, según el INEGI. | NO (15,095), SI (851), CROQUIS (277). Las SI son las rurales que también están en la tabla de amanzanadas. | PLANO |
| en_amanzanadas | booleano | La clave también está en la tabla de localidades amanzanadas. | Verdadero en 851, las mismas que tienen plano SI. | Derivada de CVEGEO y 26l |
| geometry | geometría | Punto de la localidad, en metros (EPSG:6372). | 16,223 puntos. | Geometría de 26lpr |

## Reglas de limpieza

- Lectura: cada capa directo del zip con `/vsizip/`, sin extraerlo, con la codificación ISO-8859-1 y EPSG:6372 fijo.
- Filas: se conservan todas.
- Claves: texto con sus ceros a la izquierda. En las localidades puntuales, cvegeo son los primeros 9 dígitos de CVEGEO, que trae 16 caracteres: entidad, municipio, localidad, AGEB y manzana.
- Columnas descartadas: CVE_MZA de 26lpr, porque siempre vale 800.
- Categorías (ambito y plano): en mayúsculas y sin acentos (Á, É, Í, Ó, Ú y Ü), como en SALUD-001. Rural pasa a RURAL y Si a SI.
- Nombres (municipio y localidad): como vienen, solo sin espacios al inicio ni al final y con un solo espacio entre palabras. Se corrigieron 13 nombres de localidades puntuales, como "Ninguno [Rolando Navarro]", que traía dos espacios entre el nombre y el apellido. No se corrigen acentos. "Ninguno" no pasa a nulo.
- municipio en las tablas de localidades: sale de la capa 26mun por cve_mun.
- area_km2: área de la geometría en EPSG:6372 entre 1,000,000, sin redondear. EPSG:6372 no conserva las áreas y las agranda 0.13 %: el estado mide 180,633.84 km² en EPSG:6372 y 180,399.81 km² sobre el elipsoide (EDA, sección 3.1).
- Geometrías: completas, sin simplificar, en EPSG:6372 (metros).

## Reglas de calidad

Están en `tests/test_inegi_geo_001.py` y se omiten si falta cualquiera de los tres archivos procesados. No usan conteos fijos.

- cvegeo única en cada tabla, que empieza con 26 y es igual a la concatenación de sus partes: 5 dígitos en municipios (cve_ent y cve_mun) y 9 en localidades (cve_ent, cve_mun y cve_loc).
- cve_ent de 2 dígitos, cve_mun de 3 y cve_loc de 4. cve_ageb de 3 dígitos y un dígito o una letra.
- Municipios con claves de 001 a 072, sin faltantes ni sobrantes.
- Geometrías no nulas, no vacías y válidas, y EPSG:6372 en las tres tablas.
- El punto interior de cada localidad amanzanada y el punto de cada localidad puntual caen en el municipio de su clave.
- en_amanzanadas es verdadero justo cuando plano es SI.
- Las claves que están en las dos tablas de localidades son las marcadas en en_amanzanadas y las de las amanzanadas RURAL.
- Ningún municipio ni localidad trae Ã, Â o el carácter de reemplazo (�), que son señales de mala codificación.
- Sin nulos en las columnas clave: todas menos geometry.

## Preguntas sobre los datos

- ¿Qué significa "Ninguno"? No es un nulo. Es la regla del INEGI para las localidades sin nombre geográfico: "Cuando la localidad carezca de nombre geográfico se le asignará el vocablo Ninguno y una referencia entre corchetes" (Guía de aplicación de la Norma Técnica del Marco Geoestadístico, sección 4.4.2.2.2, inciso a, criterio 6: https://ceieg.veracruz.gob.mx/wp-content/uploads/sites/21/2025/06/AnexoIII_ntmg2025.pdf). En las localidades puntuales, 405 nombres empiezan con "Ninguno": 95 sin referencia y 310 con una, como "Ninguno [Familia Escalante]". En las amanzanadas hay 1: "Ninguno [Ejido Ampliación Frontera]" (cvegeo 260171335).
- ¿Por qué 851 localidades están en las dos tablas? Son las localidades rurales amanzanadas: tienen polígono en 26l y punto en 26lpr, con plano SI. En las 851, el nombre y el municipio coinciden, y el punto cae dentro del polígono. Para contar localidades sin repetir, se suman las amanzanadas y las puntuales con en_amanzanadas falso: 16,327.
- ¿Por qué se fija EPSG:6372? Las 16 capas del zip usan la misma proyección, pero sus .prj la nombran distinto: 5 "Mexico ITRF2008 / LCC" y 11 "MEXICO_ITRF_2008_LCC" (EDA, sección 2). Sin fijarla, GeoPandas no reconoce el código EPSG de 26l y la toma como distinta a la de 26mun; al cruzarlas avisa "CRS mismatch". Sus parámetros son los de EPSG:6372, así que fijarla no mueve ninguna coordenada.
- ¿Qué localidades rebasan su municipio? El INEGI marca 2 en Sonora, en los catálogos `localidades_urbanas_que_rebasan_su_municipio.csv` y `localidades_rurales_que_rebasan_su_municipio.csv` del zip:
  - Heroica Caborca (260170001, urbana, Caborca): 56,174.6 m² de su polígono caen en Pitiquito, el 0.18 % de su área.
  - Campestre el Potrero (260430485, rural, Nogales): 48,213.2 m² caen en Imuris, el 16.669 % de su área.

  Su punto interior sí cae en su municipio y su clave no cambia. Otros 44 polígonos salen de su municipio por 1.6 m² o menos (EDA, sección 3.3). En Sonora no hay localidades isla.
