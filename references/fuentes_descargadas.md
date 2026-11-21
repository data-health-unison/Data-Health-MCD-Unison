# Fuentes descargadas

Archivo generado por `health_data.ingestion.descarga` a partir de `catalog/ingestions.csv`. No editar a mano.

## CONEVAL-ACC-001: Grado de accesibilidad a carretera pavimentada 2020 (GACP)

Grado de accesibilidad a carretera pavimentada de cada localidad del país, con sus tres componentes: distancia a carretera pavimentada, tiempo al centro de servicios más cercano y transporte público a la cabecera municipal. Población del Censo 2020.

- Fuente: CONEVAL, coneval.org.mx
- Descarga: https://www.coneval.org.mx/Medicion/MP/Documents/Accesibilidad_carretera/2020/Shapefile_localidades_componentes_GACP_CONEVAL.zip
- Fecha de descarga: 16/10/2026 09:30
- Archivo crudo: `data/raw/coneval_gacp2020_localidades.zip`
- SHA-256: `f3b55b871607987eabaec555f33a864cb0d4f43f6cc785a8c3d9351f9861faca`

Publicado el 15/06/2021. Licencia CC BY-NC 2.5 MX: uso no comercial y citando la fuente. CONEVAL desapareció en 2025; si el enlace deja de funcionar, buscar la copia que resguarda el INEGI. Metodología: https://www.coneval.org.mx/Medicion/MP/Documents/Accesibilidad_carretera/2020/Documento_metodologico_GACP_2020.pdf

## INEGI-POP-001: Principales resultados por localidad (ITER) - Censo 2020 Sonora

Principales resultados por localidad del Censo de Población y Vivienda 2020 para Sonora. Un CSV con una fila por localidad, más los totales del estado y de cada municipio y los acumulados de las localidades de una y dos viviendas.

- Fuente: INEGI, inegi.org.mx
- Descarga: https://www.inegi.org.mx/contenidos/programas/ccpv/iter/zip/iter2020/iter_26csv20.zip
- Fecha de descarga: 12/10/2026 13:12
- Archivo crudo: `data/raw/iter_26csv20.zip`
- SHA-256: `3f3795a7963d9ccdba0b19f61f7b70326ee3a48ef5af6b6b65486ff53542c366`

Las columnas se describen en https://www.inegi.org.mx/app/scitel/doc/descriptor/fd_iter_cpv2020.pdf.

## SALUD-001: Establecimientos de salud (CLUES)

Catálogo nacional de establecimientos de salud. Una fila por CLUES con institución, tipología, nivel de atención, estatus de operación, domicilio, claves geográficas y coordenadas.

- Fuente: Secretaría de Salud, gobi.salud.gob.mx
- Descarga: https://gobi.salud.gob.mx/gobi/catalogos/catalogosmaestros/ESTABLECIMIENTO_SALUD_202608.xlsx
- Fecha de descarga: 11/10/2026 09:47
- Archivo crudo: `data/raw/ESTABLECIMIENTO_SALUD_202608.xlsx`
- SHA-256: `5a1cfbe7062b41d9e51249aa4b5fc8a1e623e935882e97fb5f0aac797165c95b`

El nombre del archivo dice 202608, pero trae movimientos hasta el 22/09/2026.

## INEGI-GEO-001: Marco Geoestadístico 2025

Cartografía de Sonora en shapefile: límites del estado y de los municipios, AGEB, localidades amanzanadas (polígonos) y rurales (puntos), manzanas, vialidades y servicios.

- Fuente: INEGI, inegi.org.mx
- Descarga: https://www.inegi.org.mx/contenidos/productos/prod_serv/contenidos/espanol/bvinegi/productos/geografia/marcogeo/794551163061/26_sonora.zip
- Fecha de descarga: 13/10/2026 12:36
- Archivo crudo: `data/raw/mg2025_26_sonora.zip`
- SHA-256: `d7ba6400ba89a0925a38dd67a0d0228f5d99a47e135667c48105c4732bbf0188`

Producto 794551163061, con fecha de referencia 31/07/2025 según sus metadatos. Las coordenadas están en metros (EPSG:6372).

## INEGI-RESLOC-001: Características de las localidades 2020 - Sonora

Características de las localidades de Sonora captadas en 2020, con disponibilidad de transporte público, frecuencia y tiempo a la cabecera municipal.

- Fuente: INEGI, inegi.org.mx
- Descarga: https://www.inegi.org.mx/contenidos/programas/ccpv/iter/zip/resloc2020/resloc_26csv2020.zip
- Fecha de descarga: 19/11/2026 15:03
- Archivo crudo: `data/raw/resloc_26csv2020.zip`
- SHA-256: `69902ccba5e2e144132ceec3bc044be79e2e17269006305ce7fa66a0fea9c81a`

Descriptor: https://www.inegi.org.mx/app/scitel/doc/descriptor/FD_RESLOC_CPV2020.pdf

## SONORA-URG-001: Atención de urgencias 2018–2022

Conteos de urgencias por establecimiento, periodo y diagnóstico. El archivo contiene registros para 17 municipios de Sonora.

- Fuente: Servicios de Salud de Sonora
- Descarga: https://datos.sonora.gob.mx/dataset/318b9551-47a1-4e6b-a194-232ea5a08d43/resource/3bff8e8d-424e-4da3-878f-816a338e614e/download/202209261845420-file-1.xlsx
- Fecha de descarga: 19/11/2026 15:03
- Archivo crudo: `data/raw/sonora_urgencias_2018_2022.xlsx`
- SHA-256: `1e9edac5716186703f8bf751b0bdea9c9852a103fb8eeb1e6172f881cbfadd7a`

El libro contiene CLUES y Total_Urgencias, con desglose por mes y año. Recurso de uso no comercial. Diccionario: https://datos.sonora.gob.mx/dataset/318b9551-47a1-4e6b-a194-232ea5a08d43/resource/355da8aa-8544-4f32-b942-f54e007dd49b/download/diccionario-atencion-de-urgencias.csv

## CONAPO-MARG-001: Índice de marginación por localidad 2020

Base nacional del índice y grado de marginación y sus indicadores socioeconómicos por localidad en 2020.

- Fuente: CONAPO
- Descarga: https://raw.githubusercontent.com/IndiceMx/IM_2020/main/IML_2020.xlsx
- Fecha de descarga: 19/11/2026 15:03
- Archivo crudo: `data/raw/IML_2020.xlsx`
- SHA-256: `ac6ebec96713187edf909e913172d371a9c1f2e78182968d2d5d9de5e68913fe`

Libro nacional publicado en el repositorio IndiceMx; el procesamiento conserva Sonora. Ficha: https://www.datos.gob.mx/dataset/indices_marginacion/resource/a80656ca-ef16-435f-8fac-ad15d2874adc

## INEGI-RNC-001: Red Nacional de Caminos 2025

Edición nacional 2025 de la red de transporte terrestre, distribuida como GeoPackage en un ZIP.

- Fuente: INEGI, SICT e IMT
- Descarga: https://rnc.imt.mx/recursos/ShapeFiles/Red_Nacional_de_Caminos_2025.zip
- Fecha de descarga: 19/11/2026 15:04
- Archivo crudo: `data/raw/Red_Nacional_de_Caminos_2025.zip`
- SHA-256: `f6cb5dcb5d52b29461146830edc6050ac7e0022ba7d81558995629547c96ed6e`

Se descarga por separado debido al tamaño del archivo nacional. Documento técnico: https://www.inegi.org.mx/contenidos/productos/prod_serv/contenidos/espanol/bvinegi/productos/nueva_estruc/889463927464.pdf
