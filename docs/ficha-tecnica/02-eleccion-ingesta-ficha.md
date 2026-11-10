# 2. Elección de datasets e ingesta

## Técnicas y herramientas

Técnicas: catálogo de fuentes con estados (propuesta, aprobada, diferida) y revisión por otro integrante; descarga del archivo sin modificar; validación de firma e integridad (ZIP, libro de Excel, página HTML de error en lugar del archivo); huella SHA-256 y registro automático de cada descarga; reintentos con reanudación de descargas incompletas. Para la API: caché de consultas, rotación de tokens con cuota diaria y reintentos con esperas crecientes.

Herramientas: Python con requests y SQLite; configuración en YAML; Make y Docker para correr los pasos; pruebas con pytest.

## Fuentes elegidas

| Fuente | Institución | Qué aporta | Nivel | Formato | Prioridad |
|---|---|---|---|---|---|
| ITER (INEGI-POP-001) | INEGI | Población, coordenadas e indicadores de vulnerabilidad | Localidad | CSV en ZIP | Alta |
| CLUES (SALUD-001) | Secretaría de Salud | Ubicación, nivel de atención y estatus de cada establecimiento | Establecimiento | XLSX | Alta |
| SAKBÉ (INEGI-ROUTE-001) | INEGI | Distancia y tiempo por carretera | Ruta | API JSON | Alta |
| Marco Geoestadístico (INEGI-GEO-001) | INEGI | Límites, geometrías y claves para validar ubicaciones | Municipio y localidad | Shapefile en ZIP | Media |
| GACP (CONEVAL-ACC-001) | CONEVAL | Aislamiento de cada localidad; respaldo cuando SAKBÉ no da ruta | Localidad | Shapefile en ZIP | Media |

Criterio: cubrir las tres piezas de la pregunta (dónde vive la gente, dónde están los servicios y cuánto se tarda en llegar) al nivel de localidad, con fuentes oficiales y públicas que se unen por clave geoestadística.

## Fuentes diferidas

| Fuente | Institución | Por qué no se usa |
|---|---|---|
| Lesiones atendidas (DGIS-LES-001) | DGIS | Responde otra pregunta y solo cubre lesiones con atención prehospitalaria; posible uso futuro para validar tiempos de traslado |
| Intercensal 2025, municipal (INEGI-EIC-MUN-001) | INEGI | Solo nivel municipal y de otro año que el ITER; posible contexto en el tablero |
| Intercensal 2025, localidades de 50,000 y más (INEGI-EIC-LOC-001) | INEGI | No cubre las localidades rurales y pequeñas, que son el centro del estudio |

## Resumen de la ingesta

| Fuente | Archivo crudo o consulta | Fecha | Validación | Condiciones de uso |
|---|---|---|---|---|
| ITER | `iter_26csv20.zip` | 12/10/2026 | ZIP íntegro; huella registrada | Libre uso del INEGI, por verificar |
| CLUES | `ESTABLECIMIENTO_SALUD_202608.xlsx` | 11/10/2026 | Libro de Excel íntegro; huella registrada | Datos abiertos de Salud, por verificar |
| Marco Geoestadístico | `mg2025_26_sonora.zip` | 13/10/2026 | ZIP íntegro; huella registrada | Libre uso del INEGI, por verificar |
| GACP | `coneval_gacp2020_localidades.zip` | 16/10/2026 | ZIP íntegro; huella registrada | CC BY-NC 2.5 MX: uso no comercial, citando la fuente |
| SAKBÉ | Consultas guardadas en `data/interim/sakbe_cache.sqlite` | 16 al 18/10/2026 | Respuestas de error y de cuota separadas de las rutas válidas; ruta real para el 99.2 % de las localidades | Citar a INEGI y a la API de Ruteo SAKBÉ v3.1 |

Reglas: un archivo que ya existe no se vuelve a descargar, y si su huella no es la registrada, el proceso se detiene en vez de usarlo. La API va desacoplada del resto: `make rutas` consulta y gasta cuota; `make data` arma todo solo con lo que ya está en caché. Los tokens se leen del entorno y nunca se guardan en el repositorio, la caché ni las bitácoras.

Límites: el ITER es de 2020 y CLUES de 2026; el nombre del archivo de CLUES cambia cada mes, así que una versión nueva requiere cambiar la configuración; CONEVAL desapareció en 2025 y su enlace puede dejar de funcionar; INEGI no documenta el límite de SAKBÉ (se usan 10,000 consultas por token al día, debajo de las 11,414 que aceptó un token sin rechazo), y sus tiempos son en automóvil y en condiciones óptimas; la validación de la descarga revisa el formato, no el contenido, que se revisa en la exploración.

El detalle de cada fuente y la decisión sobre ella están en `catalog/datasets.csv`; las URL y notas, en `config/fuentes_health.yaml`; las fechas y huellas de descarga, en `catalog/ingestions.csv` y `references/fuentes_descargadas.md`; el código, en `src/health_data/ingestion/`, con sus pruebas en `tests/test_descarga.py` y `tests/test_sakbe.py`.
