# Fuentes descargadas

Archivo generado por `health_data.ingestion.descarga` a partir de `catalog/ingestions.csv`. No editar a mano.

## INEGI-POP-001: Principales resultados por localidad (ITER) - Censo 2020

Principales resultados por localidad del Censo de Población y Vivienda 2020 para Sonora. Un CSV con una fila por localidad, más los totales del estado y de cada municipio y los acumulados de las localidades de una y dos viviendas.

- Fuente: INEGI
- Página de la fuente: https://www.inegi.org.mx/app/scitel/Default?ev=9
- Edición: 2020
- Descarga: https://www.inegi.org.mx/contenidos/programas/ccpv/iter/zip/iter2020/iter_26csv20.zip
- Fecha de descarga: 12/10/2026 13:12
- Archivo crudo: `data/raw/iter_26csv20.zip`
- SHA-256: `3f3795a7963d9ccdba0b19f61f7b70326ee3a48ef5af6b6b65486ff53542c366`

Las columnas se describen en https://www.inegi.org.mx/app/scitel/doc/descriptor/fd_iter_cpv2020.pdf.

## SALUD-001: Establecimientos de salud (CLUES)

Catálogo nacional de establecimientos de salud. Una fila por CLUES con institución, tipología, nivel de atención, estatus de operación, domicilio, claves geográficas y coordenadas.

- Fuente: Secretaría de Salud
- Página de la fuente: https://gobi.salud.gob.mx/
- Edición: 2026-08
- Descarga: https://gobi.salud.gob.mx/gobi/catalogos/catalogosmaestros/ESTABLECIMIENTO_SALUD_202608.xlsx
- Fecha de descarga: 11/10/2026 09:47
- Archivo crudo: `data/raw/ESTABLECIMIENTO_SALUD_202608.xlsx`
- SHA-256: `5a1cfbe7062b41d9e51249aa4b5fc8a1e623e935882e97fb5f0aac797165c95b`

El nombre del archivo dice 202608, pero trae movimientos hasta el 22/09/2026.

## INEGI-GEO-001: Marco Geoestadístico

Cartografía de Sonora en shapefile: límites del estado y de los municipios, AGEB, localidades amanzanadas (polígonos) y rurales (puntos), manzanas, vialidades y servicios.

- Fuente: INEGI
- Página de la fuente: https://www.inegi.org.mx/app/biblioteca/ficha.html?upc=794551163061
- Edición: 2025-07
- Descarga: https://www.inegi.org.mx/contenidos/productos/prod_serv/contenidos/espanol/bvinegi/productos/geografia/marcogeo/794551163061/26_sonora.zip
- Fecha de descarga: 13/10/2026 12:36
- Archivo crudo: `data/raw/mg2025_26_sonora.zip`
- SHA-256: `d7ba6400ba89a0925a38dd67a0d0228f5d99a47e135667c48105c4732bbf0188`

Producto 794551163061, con fecha de referencia 31/07/2025 según sus metadatos. Las coordenadas están en metros (EPSG:6372).

## CONEVAL-ACC-001: Grado de accesibilidad a carretera pavimentada (GACP) por localidad

Grado de accesibilidad a carretera pavimentada de cada localidad del país, con sus tres componentes: distancia a carretera pavimentada, tiempo al centro de servicios más cercano y transporte público a la cabecera municipal. Población del Censo 2020.

- Fuente: CONEVAL
- Página de la fuente: https://www.coneval.org.mx/Medicion/Paginas/Grado_accesibilidad_carretera.aspx
- Edición: 2020
- Descarga: https://www.coneval.org.mx/Medicion/MP/Documents/Accesibilidad_carretera/2020/Shapefile_localidades_componentes_GACP_CONEVAL.zip
- Fecha de descarga: 16/10/2026 09:30
- Archivo crudo: `data/raw/coneval_gacp2020_localidades.zip`
- SHA-256: `f3b55b871607987eabaec555f33a864cb0d4f43f6cc785a8c3d9351f9861faca`

Publicado el 15/06/2021. Licencia CC BY-NC 2.5 MX: uso no comercial y citando la fuente. CONEVAL desapareció en 2025; si el enlace deja de funcionar, buscar la copia que resguarda el INEGI. Metodología: https://www.coneval.org.mx/Medicion/MP/Documents/Accesibilidad_carretera/2020/Documento_metodologico_GACP_2020.pdf
